package com.starlightnews.backend.domain.article.analysis;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisBatchResult.StopReason;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Halt;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Retryable;
import com.starlightnews.backend.domain.article.analysis.dto.ArticleAnalyzeRequest;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.repository.ArticleRepository.AnalysisTarget;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Limit;
import org.springframework.stereotype.Service;

/**
 * 분석 대기 중인 기사를 한 회차만큼 AI 분석에 넘긴다.
 *
 * <p><b>한 건씩 차례로 부른다.</b> AI 워커는 CPU 하나에서 한 번에 한 기사를 추론한다. 동시에 보내면
 * 워커 앞에 줄만 서다가 뒤쪽 요청이 타임아웃으로 끊긴다.
 *
 * <p>회차를 끝까지 돌지 않고 멈추는 경우가 셋이다. 설정 오류(어느 기사를 불러도 실패), 연속 실패
 * (AI 워커 장애로 보임), 시간 예산 초과(다음 정각의 배치와 겹침). 앞의 둘은 계속 부르면 멀쩡한
 * 기사의 시도 횟수만 태워 FAILED 로 만든다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ArticleAnalysisBatchService {

	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

	private final ArticleRepository articleRepository;
	private final ArticleAnalyzeClient analyzeClient;
	private final ArticleAnalysisRecorder recorder;
	private final ArticleAnalysisRunRecorder runRecorder;
	private final ArticleAnalysisProperties properties;

	public ArticleAnalysisBatchResult analyzePending() {
		List<AnalysisTarget> queue = articleRepository.findAnalysisQueue(
				properties.maxAttempts(), Limit.of(properties.batchSize()));
		int waitingBefore = (int) articleRepository.countAnalysisQueue(properties.maxAttempts());
		Long runId = runRecorder.start(waitingBefore, LocalDateTime.now(SEOUL));

		if (queue.isEmpty()) {
			// 회차가 돌았다는 사실은 남긴다. 기록이 비면 배치가 멈춘 것과 할 일이 없던 것을 못 가른다.
			log.info("기사 분석: 대기 중인 기사가 없습니다.");
			finish(runId, ArticleAnalysisBatchResult.empty());
			return ArticleAnalysisBatchResult.empty();
		}

		ArticleAnalysisBatchResult result;
		Backlog backlog;
		try {
			result = run(queue);
			backlog = finish(runId, result);
		} catch (RuntimeException failure) {
			// 기사 한 건의 실패는 run 안에서 삼킨다. 여기까지 온 것은 회차 자체가 끊긴 경우다.
			// 기록을 RUNNING 으로 남기면 끝난 회차인지 도는 중인지 알 수 없다.
			runRecorder.abort(runId, LocalDateTime.now(SEOUL));
			log.error("기사 분석 회차 중단", failure);
			throw failure;
		}

		log.info("기사 분석 회차 종료: 대기 {}건 중 {}건 처리 (완료 {}, 제외 {}, 재시도 {}, 포기 {}, 오류 {}), {}{}",
				waitingBefore, result.processed(), result.completed(), result.dropped(),
				result.willRetry(), result.gaveUp(), result.errors(), backlog.describe(),
				result.stopReason() == null ? "" : ", 중단: " + result.stopReason());
		return result;
	}

	/** 회차가 끝난 뒤 남은 대기를 재서 실행 기록을 닫는다. */
	private Backlog finish(Long runId, ArticleAnalysisBatchResult result) {
		Backlog backlog = backlog();
		runRecorder.finish(runId, result, backlog.waiting(), backlog.oldestMinutes(),
				LocalDateTime.now(SEOUL));
		return backlog;
	}

	private Backlog backlog() {
		int waiting = (int) articleRepository.countAnalysisQueue(properties.maxAttempts());
		Long oldestMinutes = waiting == 0
				? null : articleRepository.findOldestAnalysisWaitMinutes(properties.maxAttempts());
		return new Backlog(waiting, oldestMinutes);
	}

	/** 회차가 끝난 뒤 남은 대기. */
	private record Backlog(int waiting, Long oldestMinutes) {

		String describe() {
			if (waiting == 0) {
				return "남은 대기 없음";
			}
			return oldestMinutes == null
					? "남은 대기 %d건".formatted(waiting)
					: "남은 대기 %d건 (가장 오래 기다린 기사 %d시간 %d분)"
							.formatted(waiting, oldestMinutes / 60, oldestMinutes % 60);
		}
	}

	private ArticleAnalysisBatchResult run(List<AnalysisTarget> queue) {
		long deadline = System.nanoTime() + properties.timeBudget().toNanos();
		ArticleAnalysisBatchResult result = ArticleAnalysisBatchResult.empty();
		int consecutiveFailures = 0;

		for (AnalysisTarget target : queue) {
			if (System.nanoTime() >= deadline) {
				log.info("기사 분석: 시간 예산 {}을 다 써 남은 기사는 다음 회차로 넘깁니다.", properties.timeBudget());
				return result.stoppedBy(StopReason.OUT_OF_TIME);
			}

			ArticleAnalysisOutcome outcome;
			try {
				outcome = analyzeClient.analyze(toRequest(target));
				if (outcome instanceof Halt halt) {
					log.error("기사 분석: 설정 오류로 회차를 멈춥니다. (원인={})", halt.reason());
					return result.stoppedBy(StopReason.HALTED);
				}
				result = result.plus(recorder.record(target.getArticleId(), outcome));
			} catch (RuntimeException unexpected) {
				// 기사 한 건 때문에 회차가 통째로 죽지 않게 한다.
				log.error("기사 분석 반영 중 오류 (articleId={})", target.getArticleId(), unexpected);
				result = result.plusError();
				outcome = new Retryable("UNEXPECTED_ERROR");
			}

			consecutiveFailures = outcome instanceof Retryable ? consecutiveFailures + 1 : 0;
			if (consecutiveFailures >= properties.maxConsecutiveFailures()) {
				log.error("기사 분석: {}건 연속 실패해 회차를 멈춥니다. AI 워커 상태를 확인하세요.",
						consecutiveFailures);
				return result.stoppedBy(StopReason.TOO_MANY_FAILURES);
			}
		}
		return result;
	}

	private ArticleAnalyzeRequest toRequest(AnalysisTarget target) {
		return ArticleAnalyzeRequest.of(target.getArticleId(), target.getTitle(), target.getContent(),
				target.getOrganizationId(), target.getOrganizationName(), target.getPublishedAt());
	}
}

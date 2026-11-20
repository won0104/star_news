package com.starlightnews.backend.domain.article.analysis;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisBatchResult.StopReason;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisCircuitBreaker.Decision;
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
 *
 * <p>연속 실패로 멈추면 {@link ArticleAnalysisCircuitBreaker} 가 차단을 건다. 차단 중에는 회차마다 헬스체크를
 * 먼저 보고, 실패하면 기사를 건드리지 않고 건너뛴다. 통과하면 첫 실패 한 번에 멈추는 시험 회차로 돈다.
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
	private final ArticleAnalysisCircuitBreaker circuitBreaker;

	public ArticleAnalysisBatchResult analyzePending() {
		Decision decision = circuitBreaker.beforeRound();
		if (decision == Decision.SKIP) {
			return skipWhileOpen();
		}
		boolean probing = decision == Decision.PROBE;

		List<AnalysisTarget> queue = articleRepository.findAnalysisQueue(
				properties.maxAttempts(), Limit.of(properties.batchSize()));
		int waitingBefore = (int) articleRepository.countAnalysisQueue(properties.maxAttempts());
		Long runId = runRecorder.start(waitingBefore, LocalDateTime.now(SEOUL));

		if (queue.isEmpty()) {
			// 회차가 돌았다는 사실은 남긴다. 기록이 비면 배치가 멈춘 것과 할 일이 없던 것을 못 가른다.
			log.info("기사 분석: 대기 중인 기사가 없습니다.");
			finish(runId, ArticleAnalysisBatchResult.empty());
			// 시험 회차였다면 헬스체크는 통과했고 부를 기사가 없을 뿐이다. 차단을 풀어 둔다.
			circuitBreaker.afterRound(null);
			return ArticleAnalysisBatchResult.empty();
		}

		ArticleAnalysisBatchResult result;
		Backlog backlog;
		try {
			result = run(queue, probing);
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
		circuitBreaker.afterRound(result.stopReason());
		return result;
	}

	/**
	 * 차단 중이고 헬스체크도 실패한 회차. 기사를 하나도 부르지 않는다.
	 *
	 * <p>그래도 실행 기록은 남긴다. 기록이 비면 배치가 멈춘 것인지 차단으로 건너뛴 것인지 가를 수 없고,
	 * 장애 동안 대기가 얼마나 쌓였는지도 볼 수 없다.
	 */
	private ArticleAnalysisBatchResult skipWhileOpen() {
		int waiting = (int) articleRepository.countAnalysisQueue(properties.maxAttempts());
		Long runId = runRecorder.start(waiting, LocalDateTime.now(SEOUL));
		ArticleAnalysisBatchResult skipped = ArticleAnalysisBatchResult.empty().stoppedBy(StopReason.CIRCUIT_OPEN);
		Backlog backlog = finish(runId, skipped);
		log.warn("기사 분석: AI 장애로 차단 중이고 FastAPI 헬스체크도 실패해 회차를 건너뜁니다. (차단 시작 {}, {})",
				circuitBreaker.openedAt(), backlog.describe());
		return skipped;
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

	/**
	 * @param probing 차단 중 시험 회차인지. 그렇다면 워커가 한 번이라도 응답할 때까지는 첫 실패에 멈춘다.
	 *                헬스체크는 FastAPI 만 확인해서, 워커가 여전히 죽어 있으면 평소 한도(5건)만큼 기사를
	 *                태우게 된다
	 */
	private ArticleAnalysisBatchResult run(List<AnalysisTarget> queue, boolean probing) {
		long deadline = System.nanoTime() + properties.timeBudget().toNanos();
		ArticleAnalysisBatchResult result = ArticleAnalysisBatchResult.empty();
		int consecutiveFailures = 0;
		int failureLimit = probing ? 1 : properties.maxConsecutiveFailures();

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

			if (outcome instanceof Retryable) {
				consecutiveFailures++;
			} else {
				// 워커가 응답했다. 시험 회차라도 이제부터는 평소 한도로 판단한다.
				consecutiveFailures = 0;
				failureLimit = properties.maxConsecutiveFailures();
			}
			if (consecutiveFailures >= failureLimit) {
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

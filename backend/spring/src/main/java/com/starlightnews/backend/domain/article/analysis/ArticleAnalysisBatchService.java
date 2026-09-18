package com.starlightnews.backend.domain.article.analysis;

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

	private final ArticleRepository articleRepository;
	private final ArticleAnalyzeClient analyzeClient;
	private final ArticleAnalysisRecorder recorder;
	private final ArticleAnalysisProperties properties;

	public ArticleAnalysisBatchResult analyzePending() {
		List<AnalysisTarget> queue = articleRepository.findAnalysisQueue(
				properties.maxAttempts(), Limit.of(properties.batchSize()));
		if (queue.isEmpty()) {
			log.info("기사 분석: 대기 중인 기사가 없습니다.");
			return ArticleAnalysisBatchResult.empty();
		}

		ArticleAnalysisBatchResult result = run(queue);

		log.info("기사 분석 회차 종료: 대상 {}건, 처리 {}건 (완료 {}, 제외 {}, 재시도 {}, 포기 {}, 오류 {}){}",
				queue.size(), result.processed(), result.completed(), result.dropped(),
				result.willRetry(), result.gaveUp(), result.errors(),
				result.stopReason() == null ? "" : ", 중단: " + result.stopReason());
		return result;
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

package com.starlightnews.backend.domain.article.analysis;

import java.util.concurrent.atomic.AtomicLong;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisCircuitBreaker.Transition;
import com.starlightnews.backend.global.alert.AlertNotifier;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

/**
 * 기사 분석 회차의 지표를 남기고, 사람이 손대야 하는 결과만 알린다.
 *
 * <p>실행 기록(article_analysis_runs)은 DB 에 남지만 누가 들여다봐야 의미가 있다. 지표는 추세(처리량,
 * 밀린 정도)를 보고 경보를 걸 수 있게 하고, 알림은 지금 바로 봐야 하는 일만 보낸다.
 *
 * <ul>
 *   <li>{@code article.analysis.rounds{status}}: 회차 결과별 횟수. 상태는 {@link ArticleAnalysisRunStatus}</li>
 *   <li>{@code article.analysis.articles{outcome}}: 기사 처리 결과별 건수</li>
 *   <li>{@code article.analysis.backlog}: 마지막 회차가 끝난 뒤 남은 대기 수</li>
 *   <li>{@code article.analysis.backlog.oldest.wait.minutes}: 남은 대기 중 가장 오래 기다린 시간(분). 대기가 없으면 0</li>
 *   <li>{@code article.analysis.circuit.open}: AI 장애 차단 중이면 1</li>
 * </ul>
 *
 * <p>알림은 설정 오류(HALTED), 예외 중단(ABORTED), 연속 실패로 차단을 걸 때, 차단을 풀 때 보낸다.
 * 차단 중 시험 회차가 또 실패해도 다시 알리지 않는다. 이미 알린 장애를 매시간 되풀이하면 알림을 무시하는
 * 버릇만 든다. 차단 중이라는 사실은 지표와 실행 기록(CIRCUIT_OPEN)으로 계속 보인다.
 */
@Component
public class ArticleAnalysisMonitor {

	private final MeterRegistry registry;
	private final AlertNotifier notifier;
	private final AtomicLong backlog = new AtomicLong();
	private final AtomicLong oldestWaitMinutes = new AtomicLong();

	public ArticleAnalysisMonitor(MeterRegistry registry, AlertNotifier notifier,
			ArticleAnalysisCircuitBreaker circuitBreaker) {
		this.registry = registry;
		this.notifier = notifier;
		Gauge.builder("article.analysis.backlog", backlog, AtomicLong::get)
				.description("마지막 분석 회차가 끝난 뒤 남은 분석 대기 기사 수")
				.register(registry);
		Gauge.builder("article.analysis.backlog.oldest.wait.minutes", oldestWaitMinutes, AtomicLong::get)
				.description("남은 분석 대기 중 가장 오래 기다린 기사의 대기 시간(분)")
				.baseUnit("minutes")
				.register(registry);
		Gauge.builder("article.analysis.circuit.open", circuitBreaker, breaker -> breaker.isOpen() ? 1 : 0)
				.description("AI 장애로 분석을 차단 중이면 1")
				.register(registry);
	}

	/**
	 * 끝난 회차를 남긴다. 차단으로 건너뛴 회차도 여기로 온다.
	 *
	 * @param backlog    회차가 끝난 뒤 남은 대기
	 * @param transition 이 회차로 차단 상태가 바뀐 방향
	 */
	void roundFinished(ArticleAnalysisBatchResult result, ArticleAnalysisBacklog backlog, Transition transition) {
		ArticleAnalysisRunStatus status = ArticleAnalysisRunStatus.of(result.stopReason());
		registry.counter("article.analysis.rounds", "status", status.name()).increment();
		countArticles(result);
		this.backlog.set(backlog.waiting());
		this.oldestWaitMinutes.set(backlog.oldestMinutes() == null ? 0 : backlog.oldestMinutes());

		String summary = "처리 %d건(완료 %d, 재시도 %d, 포기 %d, 오류 %d), %s".formatted(
				result.processed(), result.completed(), result.willRetry(), result.gaveUp(), result.errors(),
				backlog.describe());

		if (status == ArticleAnalysisRunStatus.HALTED) {
			notifier.send("기사 분석 회차가 설정 오류로 멈췄습니다. 내부 API 키 설정을 확인하세요. " + summary);
		}
		if (transition == Transition.OPENED) {
			notifier.send("기사 분석이 연속 실패로 멈춰 AI 장애 차단을 걸었습니다. AI 워커 상태를 확인하세요. "
					+ "다음 회차부터 헬스체크가 통과할 때만 분석합니다. " + summary);
		}
		if (transition == Transition.CLOSED) {
			notifier.send("기사 분석 AI 장애 차단을 풀었습니다. 시험 회차가 정상으로 끝났습니다. " + summary);
		}
	}

	/** 회차가 예외로 끊겼다. 예외 메시지에는 SQL·주소가 실릴 수 있어 종류만 알린다. */
	void roundAborted(RuntimeException failure) {
		registry.counter("article.analysis.rounds", "status", ArticleAnalysisRunStatus.ABORTED.name()).increment();
		notifier.send("기사 분석 회차가 예외로 중단됐습니다. (%s) 서버 로그를 확인하세요."
				.formatted(failure.getClass().getSimpleName()));
	}

	private void countArticles(ArticleAnalysisBatchResult result) {
		increment("completed", result.completed());
		increment("dropped", result.dropped());
		increment("will_retry", result.willRetry());
		increment("gave_up", result.gaveUp());
		increment("error", result.errors());
	}

	private void increment(String outcome, int amount) {
		// 0 이어도 등록해 둔다. 한 번도 나오지 않은 결과가 지표에 아예 없으면 경보식이 비어 버린다.
		registry.counter("article.analysis.articles", "outcome", outcome).increment(amount);
	}
}

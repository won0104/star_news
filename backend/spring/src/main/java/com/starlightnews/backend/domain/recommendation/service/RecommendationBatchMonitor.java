package com.starlightnews.backend.domain.recommendation.service;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationCycleWindow;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunStatus;
import com.starlightnews.backend.global.alert.AlertNotifier;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

/**
 * 추천 생성 회차의 지표를 남기고, 사용자가 추천을 못 받게 된 경우를 알린다.
 *
 * <ul>
 *   <li>{@code recommendation.runs{status}}: 회차 결과별 횟수. COMPLETED · PARTIAL · FAILED 는
 *       {@link RecommendationRunStatus} 를 따르고, 예외로 끊긴 회차는 ABORTED 로 따로 센다. DB 기록은 둘 다
 *       FAILED 라 지표에서라도 갈라 둔다</li>
 *   <li>{@code recommendation.chunks{result}}: 묶음 수. total · failed(재시도까지 실패) · recovered(재시도로 복구)</li>
 * </ul>
 *
 * <p>알림은 회차가 예외로 끊겼을 때와 재시도까지 실패한 묶음이 남았을 때만 보낸다. 재시도로 복구된 묶음은
 * 사용자에게 영향이 없어 지표로만 남긴다.
 */
@Component
public class RecommendationBatchMonitor {

	private final MeterRegistry registry;
	private final AlertNotifier notifier;

	public RecommendationBatchMonitor(MeterRegistry registry, AlertNotifier notifier) {
		this.registry = registry;
		this.notifier = notifier;
	}

	void runFinished(RecommendationCycleWindow window, int totalChunks, int failedChunks, int recoveredChunks,
			RecommendationBatchResult result) {
		RecommendationRunStatus status = RecommendationRunStatus.of(totalChunks, failedChunks);
		registry.counter("recommendation.runs", "status", status.name()).increment();
		registry.counter("recommendation.chunks", "result", "total").increment(totalChunks);
		registry.counter("recommendation.chunks", "result", "failed").increment(failedChunks);
		registry.counter("recommendation.chunks", "result", "recovered").increment(recoveredChunks);

		if (failedChunks > 0) {
			notifier.send(("추천 생성 회차 %s(공개 %s)가 %s로 끝났습니다. 묶음 %d개 중 %d개가 재시도까지 실패해 "
					+ "%d명이 직전 회차 추천을 봅니다. (재시도로 복구 %d개)").formatted(
					window.cycle(), window.availableAt(), status, totalChunks, failedChunks,
					result.failedUsers(), recoveredChunks));
		}
	}

	/** 회차가 예외로 끊겼다. 예외 메시지에는 SQL·주소가 실릴 수 있어 종류만 알린다. */
	void runAborted(RecommendationCycleWindow window, int processedChunks, RuntimeException failure) {
		registry.counter("recommendation.runs", "status", "ABORTED").increment();
		notifier.send("추천 생성 회차 %s(공개 %s)가 예외로 중단됐습니다. (%s, 처리한 묶음 %d개) 서버 로그를 확인하세요."
				.formatted(window.cycle(), window.availableAt(), failure.getClass().getSimpleName(), processedChunks));
	}
}

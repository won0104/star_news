package com.starlightnews.backend.domain.article.reconcile;

import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 매일 03:40(KST)에 MySQL 과 Neo4j 를 대사한다.
 *
 * <p>사용자가 가장 적은 새벽에 전수 비교를 돌린다. 이 시각에도 매시 20분 분석 회차가 돌 수 있지만
 * 겹쳐도 틀린 판단을 하지 않는다. 분석 중인 기사(PROCESSING)는 대사가 건너뛰고, 되돌릴 때도 대사가 본
 * 상태 그대로일 때만 바꾼다. 되돌린 기사는 다음 분석 회차(04:20)가 가져간다.
 */
@Component
@RequiredArgsConstructor
public class GraphReconciliationScheduler {

	private final GraphReconciliationService reconciliationService;
	private final GraphReconciliationProperties properties;

	@Scheduled(cron = "${app.graph.reconciliation.cron:0 40 3 * * *}", zone = "Asia/Seoul")
	public void reconcile() {
		if (!properties.enabled()) {
			return;
		}
		reconciliationService.reconcile();
	}
}

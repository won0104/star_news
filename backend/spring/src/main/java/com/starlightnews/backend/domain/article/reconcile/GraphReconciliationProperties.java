package com.starlightnews.backend.domain.article.reconcile;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * MySQL·Neo4j 대사 배치 설정.
 *
 * @param enabled         배치를 돌릴지. 끄면 스케줄은 남아도 아무것도 하지 않는다
 * @param pageSize        한 번에 맞대 보는 기사 수. MySQL 과 Neo4j 를 이 단위로 번갈아 읽는다
 * @param requeue         어긋난 기사 중 다시 분석하면 풀리는 것을 분석 대기로 되돌릴지. 끄면 세고 기록만 한다.
 *                        되돌린 기사는 다음 분석 회차가 가져가고, 그래프에 완료 결과가 있으면 FastAPI 가
 *                        재추론 없이 그 결과를 돌려준다
 * @param maxStoredIssues 회차 하나에 상세를 남길 어긋남 수. 건수는 상한과 무관하게 모두 센다.
 *                        장애로 수천 건이 한꺼번에 어긋나도 기록 테이블이 그만큼 불어나지 않게 한다
 */
@Validated
@ConfigurationProperties(prefix = "app.graph.reconciliation")
public record GraphReconciliationProperties(
		boolean enabled,
		@Min(10) @Max(10_000) int pageSize,
		boolean requeue,
		@Min(0) @Max(10_000) int maxStoredIssues
) {
}

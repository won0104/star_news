package com.starlightnews.backend.domain.article.reconcile;

import com.starlightnews.backend.global.enums.AnalysisStatus;

/**
 * 대사에서 찾은 어긋남 한 건.
 *
 * @param mysqlStatus MySQL 쪽 분석 상태. MySQL 에 행이 없으면 null
 * @param mysqlNodeId MySQL 이 가리키는 노드 ID
 * @param graphNodeId 그래프에 있는 노드 ID. 그래프에 기사가 없으면 null
 */
public record ReconciliationIssue(
		ReconciliationIssueType type,
		long articleId,
		AnalysisStatus mysqlStatus,
		String mysqlNodeId,
		String graphNodeId
) {
}

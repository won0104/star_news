package com.starlightnews.backend.domain.article.reconcile;

/**
 * 대사 회차 한 번의 결과.
 *
 * @param mysqlChecked 맞대 본 MySQL COMPLETED 기사 수
 * @param graphChecked 맞대 본 그래프 Article 노드 수
 * @param requeued     분석 대기로 되돌린 기사 수
 */
public record GraphReconciliationResult(
		int mysqlChecked,
		int graphChecked,
		int missingGraph,
		int nodeIdMismatch,
		int unreflected,
		int droppedWithGraph,
		int orphanGraph,
		int requeued
) {

	/** 찾은 어긋남 전체 수. */
	public int issues() {
		return missingGraph + nodeIdMismatch + unreflected + droppedWithGraph + orphanGraph;
	}
}

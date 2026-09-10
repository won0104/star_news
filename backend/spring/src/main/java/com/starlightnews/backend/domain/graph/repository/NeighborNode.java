package com.starlightnews.backend.domain.graph.repository;

/**
 * Neo4j 에서 조회한 주변 Node 한 개. nodeType 은 enum 이름(EVENT·STORY·ENTITY·STATEMENT),
 * label 은 화면 표시 이름(없으면 null), neighborScore 는 중심 Node 와의 연결 경로로 계산한 0~1 중요도다.
 */
public record NeighborNode(
		String nodeType,
		String nodeKey,
		String label,
		double neighborScore
) {
}

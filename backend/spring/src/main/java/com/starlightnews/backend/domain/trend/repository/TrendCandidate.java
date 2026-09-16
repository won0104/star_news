package com.starlightnews.backend.domain.trend.repository;

/**
 * Neo4j 집계와 Story 중복 제거를 거친 트렌드 Event 후보.
 */
public record TrendCandidate(
		String nodeId,
		String nodeTitle,
		long articleCount
) {
}

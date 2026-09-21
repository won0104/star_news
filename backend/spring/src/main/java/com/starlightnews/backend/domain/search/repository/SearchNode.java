package com.starlightnews.backend.domain.search.repository;

import com.starlightnews.backend.domain.search.support.SearchCursor;

/**
 * Neo4j에서 정렬 점수와 함께 조회한 검색 결과 Node.
 */
public record SearchNode(
		String nodeType,
		String nodeKey,
		String label,
		int matchTier,
		int matchedTokenCount,
		int nodeTypeOrder
) {

	public SearchCursor toCursor() {
		return new SearchCursor(matchTier, matchedTokenCount, nodeTypeOrder, nodeKey);
	}
}

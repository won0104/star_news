package com.starlightnews.backend.domain.search.repository;

import java.util.List;

import com.starlightnews.backend.domain.search.support.NormalizedSearchQuery;
import com.starlightnews.backend.domain.search.support.SearchCursor;

/**
 * Event·Entity·Statement 검색 포트 (Neo4j, 읽기 전용).
 */
public interface SearchRepository {

	/**
	 * 완전 일치, 전체 Token 일치, 일부 Token 일치 순으로 cursor 이후 결과를 조회한다.
	 */
	List<SearchNode> search(NormalizedSearchQuery query, SearchCursor cursor, int limit);
}

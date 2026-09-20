package com.starlightnews.backend.domain.search.service;

import java.util.List;

import com.starlightnews.backend.domain.search.dto.SearchRequest;
import com.starlightnews.backend.domain.search.dto.SearchResultItem;
import com.starlightnews.backend.domain.search.exception.SearchErrorCode;
import com.starlightnews.backend.domain.search.repository.SearchNode;
import com.starlightnews.backend.domain.search.repository.SearchRepository;
import com.starlightnews.backend.domain.search.support.NormalizedSearchQuery;
import com.starlightnews.backend.domain.search.support.SearchCursor;
import com.starlightnews.backend.domain.search.support.SearchQueryNormalizer;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.response.CursorResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

/**
 * 검색어 정규화, 커서 검증, Neo4j 결과 페이지 조립을 담당한다.
 * Node 선택 이후의 상세·주변·관련 기사 조회는 공용 Graph API 책임이다.
 */
@Service
@RequiredArgsConstructor
public class SearchService {

	private final SearchQueryNormalizer searchQueryNormalizer;
	private final SearchRepository searchRepository;

	public CursorResponse<SearchResultItem> search(SearchRequest request) {
		NormalizedSearchQuery query = searchQueryNormalizer.normalize(request.query());
		SearchCursor cursor = request.cursor() == null
				? null : SearchCursor.decode(request.cursor(), query.fingerprint());

		List<SearchNode> found;
		try {
			found = searchRepository.search(query, cursor, request.size() + 1);
		} catch (RuntimeException exception) {
			throw new BusinessException(SearchErrorCode.SEARCH_QUERY_FAILED, exception);
		}

		boolean hasNext = found.size() > request.size();
		List<SearchNode> page = hasNext ? List.copyOf(found.subList(0, request.size())) : found;
		List<SearchResultItem> items = page.stream()
				.map(node -> new SearchResultItem(node.nodeType(), node.nodeKey(), node.label()))
				.toList();
		String nextCursor = hasNext
				? page.get(page.size() - 1).toCursor().encode(query.fingerprint())
				: null;

		return CursorResponse.of(items, hasNext, nextCursor);
	}
}

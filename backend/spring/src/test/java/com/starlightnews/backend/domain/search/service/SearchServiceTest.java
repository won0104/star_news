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
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class SearchServiceTest {

	private static final String FINGERPRINT = "a".repeat(64);
	private static final NormalizedSearchQuery QUERY = new NormalizedSearchQuery(
			"한국은행이 금리를 동결했다", List.of("한국은행", "금리", "동결"), FINGERPRINT,
			"*한국은행* OR *금리* OR *동결*");

	@Mock
	private SearchQueryNormalizer searchQueryNormalizer;

	@Mock
	private SearchRepository searchRepository;

	@InjectMocks
	private SearchService searchService;

	@Test
	void size보다_하나_더_조회해_다음_페이지와_cursor를_만든다() {
		SearchRequest request = new SearchRequest("검색어", null, 2);
		given(searchQueryNormalizer.normalize("검색어")).willReturn(QUERY);
		given(searchRepository.search(eq(QUERY), eq(null), eq(3))).willReturn(List.of(
				node("EVENT", "event-1", "한국은행 기준금리 동결", 2, 3, 0),
				node("ENTITY", "entity-1", "한국은행", 1, 1, 1),
				node("STATEMENT", "statement-1", "기준금리 동결", 1, 2, 2)));

		CursorResponse<SearchResultItem> response = searchService.search(request);

		assertThat(response.items()).extracting(SearchResultItem::nodeKey)
				.containsExactly("event-1", "entity-1");
		assertThat(response.hasNext()).isTrue();
		assertThat(SearchCursor.decode(response.nextCursor(), FINGERPRINT))
				.isEqualTo(new SearchCursor(1, 1, 1, "entity-1"));
		verify(searchRepository).search(QUERY, null, 3);
	}

	@Test
	void 결과가_없으면_빈_items와_hasNext_false를_반환한다() {
		SearchRequest request = new SearchRequest("검색어", null, 20);
		given(searchQueryNormalizer.normalize("검색어")).willReturn(QUERY);
		given(searchRepository.search(QUERY, null, 21)).willReturn(List.of());

		CursorResponse<SearchResultItem> response = searchService.search(request);

		assertThat(response.items()).isEmpty();
		assertThat(response.hasNext()).isFalse();
		assertThat(response.nextCursor()).isNull();
	}

	@Test
	void cursor를_검증해_repository에_전달한다() {
		SearchCursor cursor = new SearchCursor(2, 3, 0, "event-1");
		SearchRequest request = new SearchRequest("검색어", cursor.encode(FINGERPRINT), 20);
		given(searchQueryNormalizer.normalize("검색어")).willReturn(QUERY);
		given(searchRepository.search(QUERY, cursor, 21)).willReturn(List.of());

		searchService.search(request);

		verify(searchRepository).search(QUERY, cursor, 21);
	}

	@Test
	void 다른_검색어의_cursor는_repository를_호출하지_않고_INVALID_REQUEST() {
		String cursor = new SearchCursor(2, 3, 0, "event-1").encode("b".repeat(64));
		SearchRequest request = new SearchRequest("검색어", cursor, 20);
		given(searchQueryNormalizer.normalize("검색어")).willReturn(QUERY);

		Throwable thrown = catchThrowable(() -> searchService.search(request));

		assertThat(thrown).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) thrown).getErrorCode()).isEqualTo(SearchErrorCode.INVALID_REQUEST);
		verifyNoInteractions(searchRepository);
	}

	@Test
	void Neo4j_조회가_실패하면_SEARCH_QUERY_FAILED() {
		SearchRequest request = new SearchRequest("검색어", null, 20);
		given(searchQueryNormalizer.normalize("검색어")).willReturn(QUERY);
		given(searchRepository.search(eq(QUERY), eq(null), eq(21)))
				.willThrow(new RuntimeException("full-text index unavailable"));

		Throwable thrown = catchThrowable(() -> searchService.search(request));

		assertThat(thrown).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) thrown).getErrorCode()).isEqualTo(SearchErrorCode.SEARCH_QUERY_FAILED);
	}

	private SearchNode node(String type, String key, String label, int tier, int matched, int typeOrder) {
		return new SearchNode(type, key, label, tier, matched, typeOrder);
	}
}

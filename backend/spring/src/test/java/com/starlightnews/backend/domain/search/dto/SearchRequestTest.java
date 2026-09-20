package com.starlightnews.backend.domain.search.dto;

import com.starlightnews.backend.domain.search.exception.SearchErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;

class SearchRequestTest {

	@Test
	void 요청값을_검증해_서비스_입력으로_변환한다() {
		SearchRequest request = SearchRequest.of("  한국은행  ", " ", "20");

		assertThat(request.query()).isEqualTo("한국은행");
		assertThat(request.cursor()).isNull();
		assertThat(request.size()).isEqualTo(20);
	}

	@Test
	void 검색어가_없으면_INVALID_REQUEST() {
		assertInvalidRequest(catchThrowable(() -> SearchRequest.of(null, null, "20")));
		assertInvalidRequest(catchThrowable(() -> SearchRequest.of("  ", null, "20")));
	}

	@Test
	void size가_숫자가_아니거나_범위를_벗어나면_INVALID_REQUEST() {
		assertInvalidRequest(catchThrowable(() -> SearchRequest.of("검색", null, "abc")));
		assertInvalidRequest(catchThrowable(() -> SearchRequest.of("검색", null, "0")));
		assertInvalidRequest(catchThrowable(() -> SearchRequest.of("검색", null, "51")));
	}

	@Test
	void size의_최솟값과_최댓값을_허용한다() {
		assertThat(SearchRequest.of("검색", null, "1").size()).isEqualTo(1);
		assertThat(SearchRequest.of("검색", null, "50").size()).isEqualTo(50);
	}

	private void assertInvalidRequest(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) throwable).getErrorCode()).isEqualTo(SearchErrorCode.INVALID_REQUEST);
	}
}

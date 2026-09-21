package com.starlightnews.backend.domain.search.support;

import com.starlightnews.backend.domain.search.exception.SearchErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;

class SearchCursorTest {

	private static final String FINGERPRINT = "a".repeat(64);

	@Test
	void 정렬_위치를_URL_safe_Base64로_왕복한다() {
		SearchCursor original = new SearchCursor(2, 3, 1, "entity-key");

		String encoded = original.encode(FINGERPRINT);
		SearchCursor decoded = SearchCursor.decode(encoded, FINGERPRINT);

		assertThat(encoded).doesNotContain("=", "+", "/");
		assertThat(decoded).isEqualTo(original);
	}

	@Test
	void 다른_검색어의_cursor는_INVALID_REQUEST() {
		String encoded = new SearchCursor(2, 3, 1, "entity-key").encode(FINGERPRINT);

		Throwable thrown = catchThrowable(() -> SearchCursor.decode(encoded, "b".repeat(64)));

		assertInvalidRequest(thrown);
	}

	@Test
	void 손상된_cursor는_INVALID_REQUEST() {
		Throwable thrown = catchThrowable(() -> SearchCursor.decode("not-a-cursor", FINGERPRINT));

		assertInvalidRequest(thrown);
	}

	private void assertInvalidRequest(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) throwable).getErrorCode()).isEqualTo(SearchErrorCode.INVALID_REQUEST);
	}
}

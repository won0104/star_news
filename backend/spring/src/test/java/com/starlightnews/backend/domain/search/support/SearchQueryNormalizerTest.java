package com.starlightnews.backend.domain.search.support;

import java.util.stream.IntStream;

import com.starlightnews.backend.domain.search.exception.SearchErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;

class SearchQueryNormalizerTest {

	private final SearchQueryNormalizer normalizer = new SearchQueryNormalizer();

	@Test
	void 조사와_간단한_어미를_제거해_검색_Token을_만든다() {
		NormalizedSearchQuery query = normalizer.normalize("한국은행이 금리를 동결했다");

		assertThat(query.exactPhrase()).isEqualTo("한국은행이 금리를 동결했다");
		assertThat(query.tokens()).containsExactly("한국은행", "금리", "동결");
		assertThat(query.fulltextQuery()).isEqualTo("*한국은행* OR *금리* OR *동결*");
		assertThat(query.fingerprint()).hasSize(64);
	}

	@Test
	void 유니코드와_특수문자와_공백을_정리하고_중복_Token을_제거한다() {
		NormalizedSearchQuery query = normalizer.normalize("  ＳＫ하이닉스·HBM3E!!!  공급 공급  ");

		assertThat(query.exactPhrase()).isEqualTo("sk하이닉스·hbm3e!!! 공급 공급");
		assertThat(query.tokens()).containsExactly("sk하이닉스", "hbm3e", "공급");
	}

	@Test
	void 한_글자만_남는_단어는_조사를_제거하지_않는다() {
		NormalizedSearchQuery query = normalizer.normalize("회의");

		assertThat(query.tokens()).containsExactly("회의");
	}

	@Test
	void 특수문자만_있으면_INVALID_REQUEST() {
		Throwable thrown = catchThrowable(() -> normalizer.normalize("... !!!"));

		assertInvalidRequest(thrown);
	}

	@Test
	void 이모지만_있으면_INVALID_REQUEST() {
		Throwable thrown = catchThrowable(() -> normalizer.normalize("🔥 🚀"));

		assertInvalidRequest(thrown);
	}

	@Test
	void 제어_문자만_있으면_INVALID_REQUEST() {
		Throwable thrown = catchThrowable(() -> normalizer.normalize("\u0000\u0007\u001B"));

		assertInvalidRequest(thrown);
	}

	@Test
	void 인젝션_형태의_특수문자를_제거해_안전한_Fulltext_Query를_만든다() {
		NormalizedSearchQuery query = normalizer.normalize("한국은행') MATCH (n) DETACH DELETE n // 🔥");

		assertThat(query.tokens()).containsExactly("한국은행", "match", "n", "detach", "delete");
		assertThat(query.fulltextQuery())
				.isEqualTo("*한국은행* OR *match* OR *n* OR *detach* OR *delete*")
				.doesNotContain("'", "(", ")", "/");
	}

	@Test
	void Token이_20개를_초과하면_INVALID_REQUEST() {
		String input = String.join(" ", IntStream.rangeClosed(1, 21).mapToObj(number -> "토큰" + number).toList());

		Throwable thrown = catchThrowable(() -> normalizer.normalize(input));

		assertInvalidRequest(thrown);
	}

	private void assertInvalidRequest(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) throwable).getErrorCode()).isEqualTo(SearchErrorCode.INVALID_REQUEST);
	}
}

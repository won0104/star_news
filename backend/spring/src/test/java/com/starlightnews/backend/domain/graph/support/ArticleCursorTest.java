package com.starlightnews.backend.domain.graph.support;

import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Base64;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;

class ArticleCursorTest {

	private static final OffsetDateTime PUBLISHED =
			OffsetDateTime.of(2024, 1, 11, 9, 52, 15, 0, ZoneOffset.ofHours(9));

	private static String base64(String raw) {
		return Base64.getUrlEncoder().withoutPadding().encodeToString(raw.getBytes(StandardCharsets.UTF_8));
	}

	private GraphErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return (GraphErrorCode) ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 인코딩한_커서를_디코딩하면_원래_값이_복원된다() {
		ArticleCursor original = new ArticleCursor(PUBLISHED, 930001L);

		ArticleCursor restored = ArticleCursor.decode(original.encode());

		assertThat(restored).isEqualTo(original);
	}

	@Test
	void 인코딩_결과는_원시_값을_그대로_노출하지_않는다() {
		String encoded = new ArticleCursor(PUBLISHED, 930001L).encode();

		assertThat(encoded).doesNotContain(":", "|", " ", "930001");
	}

	@Test
	void base64가_아니면_INVALID_CURSOR() {
		Throwable thrown = catchThrowable(() -> ArticleCursor.decode("!!! not base64 !!!"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
	}

	@Test
	void 구분자가_없으면_INVALID_CURSOR() {
		Throwable thrown = catchThrowable(() -> ArticleCursor.decode(base64("just-text-no-delimiter")));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
	}

	@Test
	void 시각이_파싱_불가능하면_INVALID_CURSOR() {
		Throwable thrown = catchThrowable(() -> ArticleCursor.decode(base64("not-a-date|930001")));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
	}

	@Test
	void articleId가_숫자가_아니면_INVALID_CURSOR() {
		Throwable thrown = catchThrowable(
				() -> ArticleCursor.decode(base64(PUBLISHED + "|not-a-number")));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
	}
}

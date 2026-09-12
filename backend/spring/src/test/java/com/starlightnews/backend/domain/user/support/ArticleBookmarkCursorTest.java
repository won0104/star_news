package com.starlightnews.backend.domain.user.support;

import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Base64;

import com.starlightnews.backend.domain.user.exception.UserErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ArticleBookmarkCursorTest {

	@Test
	void 북마크_시각과_articleId를_불투명_문자열로_왕복한다() {
		ArticleBookmarkCursor cursor = new ArticleBookmarkCursor(
				OffsetDateTime.of(2026, 9, 1, 9, 0, 0, 123_456_000, ZoneOffset.ofHours(9)), 101L);

		ArticleBookmarkCursor decoded = ArticleBookmarkCursor.decode(cursor.encode());

		assertThat(decoded).isEqualTo(cursor);
	}

	@Test
	void 잘못된_형식은_INVALID_CURSOR이다() {
		assertThatThrownBy(() -> ArticleBookmarkCursor.decode("not-a-cursor"))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.INVALID_CURSOR));
	}

	@Test
	void articleId가_양수가_아니면_INVALID_CURSOR이다() {
		String raw = "2026-09-01T09:00:00+09:00|0";
		String encoded = Base64.getUrlEncoder().withoutPadding()
				.encodeToString(raw.getBytes(StandardCharsets.UTF_8));

		assertThatThrownBy(() -> ArticleBookmarkCursor.decode(encoded))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.INVALID_CURSOR));
	}
}

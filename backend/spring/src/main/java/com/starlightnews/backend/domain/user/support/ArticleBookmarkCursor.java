package com.starlightnews.backend.domain.user.support;

import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.Base64;

import com.starlightnews.backend.domain.user.exception.UserErrorCode;
import com.starlightnews.backend.global.error.BusinessException;

/**
 * 기사 북마크 커서. 정렬 마지막 항목의 (bookmarkedAt, articleId)를 불투명 문자열로 전달한다.
 */
public record ArticleBookmarkCursor(OffsetDateTime bookmarkedAt, long articleId) {

	private static final String DELIMITER = "|";

	/** URL-safe base64 문자열로 인코딩한다. */
	public String encode() {
		String raw = bookmarkedAt.toString() + DELIMITER + articleId;
		return Base64.getUrlEncoder().withoutPadding()
				.encodeToString(raw.getBytes(StandardCharsets.UTF_8));
	}

	/** 형식이 올바르지 않은 커서는 INVALID_CURSOR로 거부한다. */
	public static ArticleBookmarkCursor decode(String encoded) {
		try {
			String raw = new String(Base64.getUrlDecoder().decode(encoded), StandardCharsets.UTF_8);
			int split = raw.indexOf(DELIMITER);
			if (split <= 0 || split != raw.lastIndexOf(DELIMITER)) {
				throw new BusinessException(UserErrorCode.INVALID_CURSOR);
			}

			OffsetDateTime bookmarkedAt = OffsetDateTime.parse(raw.substring(0, split));
			long articleId = Long.parseLong(raw.substring(split + DELIMITER.length()));
			if (articleId <= 0) {
				throw new BusinessException(UserErrorCode.INVALID_CURSOR);
			}
			return new ArticleBookmarkCursor(bookmarkedAt, articleId);
		} catch (IllegalArgumentException | DateTimeParseException exception) {
			throw new BusinessException(UserErrorCode.INVALID_CURSOR);
		}
	}
}

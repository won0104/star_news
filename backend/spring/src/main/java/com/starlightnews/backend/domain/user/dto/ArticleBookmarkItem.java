package com.starlightnews.backend.domain.user.dto;

import java.time.OffsetDateTime;

/** 북마크 기사 목록의 한 항목. */
public record ArticleBookmarkItem(
		long articleId,
		String title,
		String publisher,
		OffsetDateTime publishedAt,
		String summary,
		OffsetDateTime bookmarkedAt
) {
}

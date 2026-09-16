package com.starlightnews.backend.domain.article.dto;

import java.time.OffsetDateTime;

import com.starlightnews.backend.global.enums.SummaryStatus;

/** 기사 상세 화면에 필요한 조회 결과. */
public record ArticleDetailResponse(
		Long articleId,
		String title,
		String organizationName,
		OffsetDateTime publishedAt,
		String summary,
		SummaryStatus summaryStatus,
		String originalUrl,
		boolean bookmarked
) {
}

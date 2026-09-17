package com.starlightnews.backend.domain.article.dto;

import com.starlightnews.backend.global.enums.SummaryStatus;

/** 기사 요약 생성 요청의 현재 결과. */
public record ArticleSummaryResponse(
		Long articleId,
		String summary,
		SummaryStatus summaryStatus
) {
}

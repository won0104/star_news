package com.starlightnews.backend.domain.article.dto;

import io.swagger.v3.oas.annotations.media.Schema;

/** 기사 요약 생성 요청의 현재 결과. */
public record ArticleSummaryResponse(
		@Schema(description = "기사 ID", example = "101")
		Long articleId,
		@Schema(description = "생성되었거나 기존에 저장된 요약. 다른 요청이 생성 중이면 null",
				nullable = true, example = "국방부는 한미 연합훈련 일정과 세부 계획을 발표했다.")
		String summary,
		@Schema(description = "요약 생성 요청의 현재 상태", example = "COMPLETED")
		ArticleSummaryStatus summaryStatus
) {
}

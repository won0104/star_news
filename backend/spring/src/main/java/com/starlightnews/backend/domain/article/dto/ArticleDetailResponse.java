package com.starlightnews.backend.domain.article.dto;

import java.time.OffsetDateTime;

import io.swagger.v3.oas.annotations.media.Schema;

/** 기사 상세 화면에 필요한 조회 결과. */
public record ArticleDetailResponse(
		@Schema(description = "기사 ID", example = "101")
		Long articleId,
		@Schema(description = "기사 제목", example = "국방부, 한미 연합훈련 일정 발표")
		String title,
		@Schema(description = "기사 발행 언론사명", example = "연합뉴스")
		String organizationName,
		@Schema(description = "언론사가 기사를 발행한 시각", example = "2026-08-31T10:00:00+09:00")
		OffsetDateTime publishedAt,
		@Schema(description = "저장되었거나 상세 조회 중 생성된 AI 요약. 다른 요청이 생성 중이면 null",
				nullable = true, example = "국방부는 한미 연합훈련 일정과 세부 계획을 발표했다.")
		String summary,
		@Schema(description = "상세 조회 응답의 요약 상태", example = "COMPLETED")
		ArticleSummaryStatus summaryStatus,
		@Schema(description = "언론사 원문 URL", example = "https://news.example.com/articles/101")
		String originalUrl,
		@Schema(description = "현재 사용자의 기사 북마크 여부. 비회원은 false", example = "false")
		boolean bookmarked
) {
}

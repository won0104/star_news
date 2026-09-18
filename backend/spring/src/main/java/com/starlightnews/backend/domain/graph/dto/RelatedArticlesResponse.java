package com.starlightnews.backend.domain.graph.dto;

import java.time.OffsetDateTime;
import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 노드 관련 기사 목록 조회 응답. 목록은 최신 발행 순이며 커서 페이지네이션을 사용한다.
 */
public record RelatedArticlesResponse(

		List<Item> articles,

		@Schema(description = "중복 제거한 전체 관련 기사 수", example = "42")
		long totalCount,

		@Schema(description = "이번 응답에 포함된 기사 수", example = "30")
		int returnedCount,

		@Schema(description = "추가로 조회할 관련 기사가 있는지", example = "true")
		boolean hasNext,

		@Schema(description = "다음 기사 묶음의 시작 커서 (hasNext=false 면 null)", nullable = true)
		String nextCursor
) {

	@Schema(name = "RelatedArticleItem")
	public record Item(

			@Schema(description = "MySQL Article PK", example = "930001")
			long articleId,

			@Schema(description = "기사 제목", example = "한국은행 1월 기준금리 동결")
			String title,

			@Schema(description = "발행 언론사명", example = "연합뉴스")
			String organizationName,

			@Schema(description = "언론사가 기사를 발행한 시각", example = "2024-01-11T09:52:15+09:00")
			OffsetDateTime publishedAt,

			@Schema(description = "현재 사용자의 기사 북마크 여부 (비로그인 false)", example = "false")
			boolean bookmarked
	) {
	}
}

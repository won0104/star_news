package com.starlightnews.backend.domain.user.dto;

import java.time.OffsetDateTime;
import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 사용자의 전체 기사 열람 기록을, 마지막으로 읽은 시각(lastReadAt) 최신순으로 담는다.
 */
public record ArticleHistoryResponse(

		List<Item> items,

		@Schema(description = "다음 열람 기록이 더 있는지", example = "true")
		boolean hasNext,

		@Schema(description = "다음 묶음의 시작 커서 (hasNext=false 면 null)", nullable = true)
		String nextCursor
) {

	@Schema(name = "ArticleHistoryItem")
	public record Item(

			@Schema(description = "MySQL Article PK", example = "930001")
			long articleId,

			@Schema(description = "기사 제목", example = "한국은행, 기준금리 동결")
			String title,

			@Schema(description = "발행 언론사명", example = "연합뉴스")
			String organizationName,

			@Schema(description = "기사의 Topic 코드", example = "ECONOMY", nullable = true)
			String topicCode,

			@Schema(description = "Topic 코드의 한글 표시명", example = "경제", nullable = true)
			String topicName,

			@Schema(description = "사용자가 이 기사를 마지막으로 읽은 시각", example = "2026-08-31T09:10:00+09:00")
			OffsetDateTime lastReadAt,

			@Schema(description = "이 기사와 연결된 Node 를 클릭한 횟수", example = "3")
			int clickCount,

			@Schema(description = "저장된 요약 앞부분. 요약이 없으면 null (이 API 에서 요약을 생성하지 않음)",
					example = "한국은행은 기준금리를 현재 수준으로 유지하기로 했다.", nullable = true)
			String summaryPreview,

			@Schema(description = "현재 사용자의 기사 북마크 여부", example = "true")
			boolean bookmarked
	) {
	}
}

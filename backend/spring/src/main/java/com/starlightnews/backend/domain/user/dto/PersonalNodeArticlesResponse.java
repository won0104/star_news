package com.starlightnews.backend.domain.user.dto;

import java.time.OffsetDateTime;
import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 개인 그래프에서 선택한 Node 와 관련된 기사 중, 사용자가 실제로 읽은 기사만 최근 읽은 순으로 담는다.
 */
public record PersonalNodeArticlesResponse(

		NodeSummary node,

		List<Item> items,

		@Schema(description = "추가로 조회할 읽은 기사가 있는지", example = "true")
		boolean hasNext,

		@Schema(description = "다음 기사 묶음의 시작 커서 (hasNext=false 면 null)", nullable = true)
		String nextCursor
) {

	public record NodeSummary(

			@Schema(description = "Node 유형 (EVENT·ENTITY·STATEMENT)", example = "ENTITY")
			String nodeType,

			@Schema(description = "Node 업무 ID(nodeId)", example = "00000024-0920-4000-8000-000000000001")
			String nodeKey,

			@Schema(description = "화면 표시 이름 (user_knowledge_nodes.node_label)", example = "한국은행")
			String title
	) {
	}

	public record Item(

			@Schema(description = "MySQL Article PK", example = "930001")
			long articleId,

			@Schema(description = "기사 제목", example = "한국은행, 기준금리 동결")
			String title,

			@Schema(description = "발행 언론사명", example = "연합뉴스")
			String organizationName,

			@Schema(description = "기사의 Topic 코드", example = "ECONOMY", nullable = true)
			String topicCode,

			@Schema(description = "사용자가 이 기사를 마지막으로 읽은 시각", example = "2026-08-31T09:10:00+09:00")
			OffsetDateTime lastReadAt,

			@Schema(description = "저장된 요약 앞부분. 요약이 없으면 null (이 API 에서 요약을 생성하지 않음)",
					example = "한국은행은 기준금리를 현재 수준으로 유지하기로 했다.", nullable = true)
			String summaryPreview,

			@Schema(description = "현재 사용자의 기사 북마크 여부", example = "true")
			boolean bookmarked
	) {
	}
}

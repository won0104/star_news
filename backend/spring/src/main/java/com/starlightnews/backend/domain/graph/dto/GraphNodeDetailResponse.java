package com.starlightnews.backend.domain.graph.dto;

import java.time.OffsetDateTime;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 그래프 Node 상세 조회 응답.
 * type·time 은 Node 유형에 따라 없을 수 있으며(null), bookmarked 는 비로그인 시 항상 false 다.
 */
public record GraphNodeDetailResponse(

		@Schema(description = "Node 유형", example = "EVENT")
		String nodeType,

		@Schema(description = "Node 의 업무 ID(nodeId)", example = "00000020-0920-4000-8000-000000000001")
		String nodeKey,

		@Schema(description = "화면에 표시할 Node 이름", example = "한국은행 기준금리 동결")
		String title,

		@Schema(description = "Entity·Statement 의 세부 유형 또는 Time 의 시간 단위", nullable = true, example = "PERSON")
		String type,

		@Schema(description = "Event 발생 시각 또는 Story 대표 시각", nullable = true, example = "2026-08-28T09:00:00+09:00")
		OffsetDateTime time,

		@Schema(description = "현재 사용자의 Node 즐겨찾기 여부", example = "true")
		boolean bookmarked
) {
}

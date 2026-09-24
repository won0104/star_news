package com.starlightnews.backend.domain.topic.dto;

import java.time.OffsetDateTime;
import java.util.List;

import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.enums.TopicCode;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 선택한 Topic을 중심으로 표시할 공개 회차와 탐색 진입 Event 목록.
 */
@Schema(name = "TopicExplorationResponse", description = "Topic별 탐색 진입 Node 응답")
public record TopicExplorationResponse(

		@Schema(description = "Topic별 탐색 공개 회차 시각 (06:00/18:00 KST). 공개된 결과가 없으면 null",
				example = "2026-09-24T18:00:00+09:00", nullable = true)
		OffsetDateTime snapshotAt,

		@Schema(description = "화면 중앙에 표시할 Topic")
		CenterTopic centerTopic,

		@Schema(description = "순위 오름차순의 탐색 진입 Event 목록 (최대 10개)")
		List<EntryNode> entryNodes
) {

	public TopicExplorationResponse {
		entryNodes = entryNodes == null ? List.of() : List.copyOf(entryNodes);
	}

	@Schema(name = "TopicExplorationCenterTopic", description = "탐색 화면 중앙에 표시할 Topic")
	public record CenterTopic(

			@Schema(description = "중심 Node 유형", example = "TOPIC")
			NodeType nodeType,

			@Schema(description = "요청한 Topic 코드", example = "ECONOMY")
			TopicCode topicCode,

			@Schema(description = "Topic 한글 표시 이름", example = "경제")
			String label
	) {
	}

	@Schema(name = "TopicExplorationEntryNode", description = "Topic별 탐색 진입 Event")
	public record EntryNode(

			@Schema(description = "저장된 개별 탐색 진입 항목 ID", example = "201")
			long entryNodeId,

			@Schema(description = "Topic·공개 회차 내 순위", example = "1")
			int rank,

			@Schema(description = "탐색 진입 Node 유형", example = "EVENT")
			NodeType nodeType,

			@Schema(description = "Neo4j 내부 ID가 아닌 Event의 업무 ID인 nodeId",
					example = "550e8400-e29b-41d4-a716-446655440000")
			String nodeKey,

			@Schema(description = "집계 시점에 저장한 Event 표시 이름", example = "한국은행 기준금리 동결")
			String label,

			@Schema(description = "05:50/17:50 직전 24시간 동안 Event를 대표로 다룬 고유 기사 수", example = "23")
			int articleCount
	) {
	}
}

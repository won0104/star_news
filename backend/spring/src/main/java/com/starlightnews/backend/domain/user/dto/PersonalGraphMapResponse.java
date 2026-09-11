package com.starlightnews.backend.domain.user.dto;

import java.time.OffsetDateTime;
import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 선택한 Topic 의 개인 지식 그래프 스냅샷. 개인 Node 는 MySQL user_knowledge_nodes 기준이며,
 * Edge 는 그 Node 들 사이의 Neo4j 관계만 담는다.
 */
public record PersonalGraphMapResponse(

		@Schema(description = "스냅샷 생성 시각", example = "2026-09-11T17:30:00+09:00")
		OffsetDateTime generatedAt,

		TopicSummary topic,

		List<Node> nodes,

		List<Edge> edges
) {

	public record TopicSummary(

			@Schema(description = "Topic 코드", example = "ECONOMY")
			String topicCode,

			@Schema(description = "화면 표시 한글명", example = "경제")
			String label
	) {
	}

	public record Node(

			@Schema(description = "그래프 내 Node 식별자 (nodeType:nodeKey)", example = "ENTITY:00000024-0920-4000-8000-000000000001")
			String id,

			@Schema(description = "Node 유형 (EVENT·ENTITY·STATEMENT)", example = "ENTITY")
			String nodeType,

			@Schema(description = "Node 업무 ID(nodeId)", example = "00000024-0920-4000-8000-000000000001")
			String nodeKey,

			@Schema(description = "화면 표시 이름 (user_knowledge_nodes.node_label)", example = "한국은행")
			String label,

			@Schema(description = "사용자가 이 Node 와 연결해 읽은 기사 수", example = "5")
			int sourceArticleCount,

			@Schema(description = "사용자 기준 중요도 0~1 정규화 값", example = "0.91")
			double weight
	) {
	}

	public record Edge(

			@Schema(description = "출발 Node id", example = "ENTITY:00000024-0920-4000-8000-000000000001")
			String sourceId,

			@Schema(description = "도착 Node id", example = "EVENT:00000020-0920-4000-8000-000000000001")
			String targetId,

			@Schema(description = "Neo4j 관계 타입", example = "ACTOR")
			String relationship,

			@Schema(description = "선 굵기·강도 표현용 0~1 표시 가중치", example = "0.82")
			double weight
	) {
	}
}

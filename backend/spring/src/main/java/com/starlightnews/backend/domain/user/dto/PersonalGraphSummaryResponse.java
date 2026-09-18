package com.starlightnews.backend.domain.user.dto;

import java.time.OffsetDateTime;
import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 내 읽기 최초 진입용 개인 지식 그래프 요약. Topic Cluster(가짜 Node)와 각 Topic 대표 개인 Node(최대 5개)를
 * 함께 반환하며, Cluster 안쪽 실제 확장은 {@code GET /users/me/graph/map} 이 담당한다.
 */
public record PersonalGraphSummaryResponse(

		@Schema(description = "스냅샷 생성 시각", example = "2026-09-11T17:30:00+09:00")
		OffsetDateTime generatedAt,

		@Schema(description = "모든 Topic Cluster 와 각 Topic 의 대표 개인 Node 목록. 개인 Node 가 없어도 Topic Cluster 는 포함된다")
		List<Node> nodes,

		@Schema(description = "Topic Cluster·대표 개인 Node 사이의 관계. 개인 Node 가 없으면 빈 배열")
		List<Edge> edges
) {

	@Schema(name = "PersonalGraphSummaryNode")
	public record Node(

			@Schema(description = "그래프 내 Node 식별자. Cluster 는 topic:{topicCode}, Node 는 nodeType:nodeKey",
					example = "topic:ECONOMY")
			String id,

			@Schema(description = "TOPIC_CLUSTER 또는 NODE", example = "TOPIC_CLUSTER")
			String kind,

			@Schema(description = "실제 Neo4j Node 유형. Cluster 면 null", example = "ENTITY", nullable = true)
			String nodeType,

			@Schema(description = "Node 업무 ID(nodeId). Cluster 면 null", nullable = true)
			String nodeKey,

			@Schema(description = "이 Node 를 화면에서 묶을 Topic", example = "ECONOMY")
			String topicCode,

			@Schema(description = "화면 표시 이름 (Cluster 는 Topic 한글명, Node 는 node_label)", example = "경제")
			String title,

			@Schema(description = "Entity.entityType 또는 Statement.statementType. 그 외 null", nullable = true)
			String type,

			@Schema(description = "연결된 읽은 기사 수", example = "5")
			int sourceArticleCount,

			@Schema(description = "사용자 기준 중요도 0~1 정규화 값", example = "0.65")
			double weight
	) {
	}

	@Schema(name = "PersonalGraphSummaryEdge")
	public record Edge(

			@Schema(description = "출발 Node id", example = "topic:ECONOMY")
			String sourceId,

			@Schema(description = "도착 Node id", example = "ENTITY:00000024-0920-4000-8000-000000000001")
			String targetId,

			@Schema(description = "BELONGS_TO_TOPIC 또는 Neo4j 관계 타입", example = "BELONGS_TO_TOPIC")
			String relationship,

			@Schema(description = "선 굵기·강도 표현용 0~1 표시 가중치", example = "0.8")
			double weight
	) {
	}
}

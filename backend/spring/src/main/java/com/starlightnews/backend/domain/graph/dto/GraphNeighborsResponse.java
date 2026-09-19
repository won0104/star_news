package com.starlightnews.backend.domain.graph.dto;

import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 주변 그래프 조회 응답. 중심 Node 1개와 neighborScore 순 주변 Node, 그 사이의 Edge 를 담는다.
 * 커서 페이지네이션을 사용하며 neighborScore 자체는 응답에 노출하지 않는다.
 */
public record GraphNeighborsResponse(

		@Schema(description = "그래프의 중심으로 선택한 Node")
		NodeSummary centerNode,

		@Schema(description = "중심 Node 를 제외한 주변 Node 목록 (neighborScore DESC, nodeType ASC, nodeKey ASC)")
		List<NodeSummary> nodes,

		@Schema(description = "centerNode 와 nodes 안에서 양 끝이 모두 포함되는 관계")
		List<Edge> edges,

		@Schema(description = "이번 응답에 포함된 주변 Node 수", example = "15")
		int returnedCount,

		@Schema(description = "추가로 조회할 주변 Node 가 있는지", example = "true")
		boolean hasNext,

		@Schema(description = "다음 묶음의 시작 커서 (hasNext=false 면 null)", nullable = true)
		String nextCursor
) {

	@Schema(name = "GraphNeighborNodeSummary")
	public record NodeSummary(

			@Schema(description = "Node 유형 (EVENT·ENTITY·STATEMENT·TIME)", example = "EVENT")
			String nodeType,

			@Schema(description = "Node 업무 ID(nodeId)", example = "00000020-0920-4000-8000-000000000001")
			String nodeKey,

			@Schema(description = "화면 표시 이름 (없으면 null)", example = "한국은행 1월 기준금리 동결", nullable = true)
			String label
	) {
	}

	@Schema(name = "GraphNeighborEdge")
	public record Edge(

			@Schema(description = "출발 Node 유형", example = "EVENT")
			String sourceNodeType,

			@Schema(description = "출발 Node 업무 ID", example = "00000020-0920-4000-8000-000000000001")
			String sourceNodeKey,

			@Schema(description = "도착 Node 유형", example = "ENTITY")
			String targetNodeType,

			@Schema(description = "도착 Node 업무 ID", example = "00000024-0920-4000-8000-000000000001")
			String targetNodeKey,

			@Schema(description = "Neo4j 관계 타입", example = "ACTOR")
			String edgeType,

			@Schema(description = "선 굵기·강도 표현용 0~1 표시 가중치", example = "0.91")
			double weight
	) {
	}
}

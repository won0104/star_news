package com.starlightnews.backend.domain.demo.dto;

import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 기사 한 건에서 만들어진 지식그래프.
 *
 * <p>화면이 그대로 그릴 수 있게 노드 목록과 간선 목록으로 준다. 간선의 {@code from}/{@code to} 는
 * 노드의 {@code nodeKey} 를 가리킨다.
 *
 * @param articleId     MySQL articles.article_id
 * @param articleNodeId Neo4j Article 의 nodeId. 그래프의 시작점이다
 */
public record DemoGraphResponse(

		@Schema(description = "저장된 기사 ID", example = "11285")
		long articleId,

		@Schema(description = "Neo4j Article 노드 키")
		String articleNodeId,

		@Schema(description = "대분류", example = "SOCIETY")
		String topicCode,

		@Schema(description = "소분류", example = "ACCIDENT")
		String subtopicCode,

		@Schema(description = "그래프 노드")
		List<DemoGraphNode> nodes,

		@Schema(description = "그래프 간선")
		List<DemoGraphEdge> edges
) {

	/**
	 * @param nodeType ARTICLE | EVENT | ENTITY | STATEMENT | TOPIC | TIME | STORY
	 * @param subType  Entity 의 세부 유형(PERSON·ORGANIZATION·LOCATION·PRODUCT). 그 밖에는 null
	 */
	public record DemoGraphNode(
			@Schema(description = "노드 키") String nodeKey,
			@Schema(description = "노드 종류", example = "EVENT") String nodeType,
			@Schema(description = "화면에 보일 이름") String label,
			@Schema(description = "Entity 세부 유형", example = "PERSON") String subType
	) {
	}

	/**
	 * @param relation COVERS | MENTIONS | CONTAINS_STATEMENT | ACTOR | TARGET | PLACE
	 *                 | CLASSIFIED_AS | OCCURRED_ON | PART_OF | PUBLISHED_BY
	 * @param primary  그 기사가 대표로 다루는 사건인지. COVERS·CLASSIFIED_AS 에만 의미가 있다
	 */
	public record DemoGraphEdge(
			@Schema(description = "출발 노드 키") String from,
			@Schema(description = "도착 노드 키") String to,
			@Schema(description = "관계 종류", example = "COVERS") String relation,
			@Schema(description = "대표 관계 여부") boolean primary
	) {
	}
}

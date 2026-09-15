package com.starlightnews.backend.domain.graph.support;

import java.util.Optional;

import com.starlightnews.backend.global.enums.NodeType;

/**
 * 관련 기사 조회가 지원되는 Node 유형과, 그 유형에 연결된 Article 을 찾는 Neo4j 관계.
 * 여기 없는 NodeType(STORY, TOPIC, TIME, ARTICLE 등)은 관련 기사 조회 대상이 아니다.
 */
public enum ArticleRelation {

	EVENT(NodeType.EVENT, "COVERS"),
	ENTITY(NodeType.ENTITY, "MENTIONS"),
	STATEMENT(NodeType.STATEMENT, "CONTAINS_STATEMENT");

	private final NodeType nodeType;
	private final String relationshipType;

	ArticleRelation(NodeType nodeType, String relationshipType) {
		this.nodeType = nodeType;
		this.relationshipType = relationshipType;
	}

	/** (Article)-[:relationshipType]->(node) 형태로 사용하는 Neo4j 관계 타입. */
	public String relationshipType() {
		return relationshipType;
	}

	/** 대상 Node 의 Neo4j Label. */
	public String nodeLabel() {
		return nodeType.label();
	}

	/** 이 관계가 가리키는 Node 유형. */
	public NodeType nodeType() {
		return nodeType;
	}

	/** 해당 NodeType 의 관련 기사 관계. 지원하지 않는 유형이면 빈 Optional. */
	public static Optional<ArticleRelation> forNodeType(NodeType nodeType) {
		for (ArticleRelation relation : values()) {
			if (relation.nodeType == nodeType) {
				return Optional.of(relation);
			}
		}
		return Optional.empty();
	}
}

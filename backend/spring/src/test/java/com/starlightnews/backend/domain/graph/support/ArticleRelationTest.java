package com.starlightnews.backend.domain.graph.support;

import com.starlightnews.backend.global.enums.NodeType;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ArticleRelationTest {

	@Test
	void 지원_유형은_관계타입과_Label을_돌려준다() {
		ArticleRelation event = ArticleRelation.forNodeType(NodeType.EVENT).orElseThrow();
		assertThat(event.relationshipType()).isEqualTo("COVERS");
		assertThat(event.nodeLabel()).isEqualTo("Event");

		ArticleRelation entity = ArticleRelation.forNodeType(NodeType.ENTITY).orElseThrow();
		assertThat(entity.relationshipType()).isEqualTo("MENTIONS");
		assertThat(entity.nodeLabel()).isEqualTo("Entity");

		ArticleRelation statement = ArticleRelation.forNodeType(NodeType.STATEMENT).orElseThrow();
		assertThat(statement.relationshipType()).isEqualTo("CONTAINS_STATEMENT");
		assertThat(statement.nodeLabel()).isEqualTo("Statement");
	}

	@Test
	void 관련_기사_조회_대상이_아닌_유형은_빈_Optional이다() {
		assertThat(ArticleRelation.forNodeType(NodeType.STORY)).isEmpty();
		assertThat(ArticleRelation.forNodeType(NodeType.TOPIC)).isEmpty();
		assertThat(ArticleRelation.forNodeType(NodeType.TIME)).isEmpty();
		assertThat(ArticleRelation.forNodeType(NodeType.ARTICLE)).isEmpty();
	}
}

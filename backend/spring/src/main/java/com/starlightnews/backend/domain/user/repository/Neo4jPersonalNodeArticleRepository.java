package com.starlightnews.backend.domain.user.repository;

import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.graph.support.ArticleRelation;
import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Neo4jClient 기반 개인 그래프 관련 기사 후보 조회.
 * 관계 타입은 파라미터화할 수 없으므로 검증된 {@link ArticleRelation} 값에서 문자열로 끼워 넣고,
 * Label 은 labels(n) 포함 여부로 필터한다.
 */
@Repository
public class Neo4jPersonalNodeArticleRepository implements PersonalNodeArticleRepository {

	private static final String FIND_RELATED_ARTICLE_IDS_CYPHER = """
			MATCH (a:Article)-[:%s]->(n {nodeId: $nodeKey})
			WHERE $label IN labels(n)
			RETURN DISTINCT a.mysqlArticleId AS articleId
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jPersonalNodeArticleRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public List<Long> findRelatedArticleIds(ArticleRelation relation, String nodeKey) {
		return neo4jClient.query(FIND_RELATED_ARTICLE_IDS_CYPHER.formatted(relation.relationshipType()))
				.bindAll(Map.of("nodeKey", nodeKey, "label", relation.nodeLabel()))
				.fetchAs(Long.class)
				.mappedBy((typeSystem, record) -> record.get("articleId").asLong())
				.all()
				.stream()
				.toList();
	}
}

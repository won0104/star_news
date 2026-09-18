package com.starlightnews.backend.domain.recommendation.repository;

import java.util.List;
import java.util.Map;

import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Neo4jClient 기반 Event 관련 기사 조회 구현.
 */
@Repository
public class Neo4jEventArticleRepository implements EventArticleRepository {

	/**
	 * 관련도 높은 순, 같으면 최신 순.
	 *
	 * <p>관련도는 COVERS 의 confidence 다. COVERS 에는 relevance 가 없다.
	 * 같은 기사가 여러 관계로 이어질 수 있어 기사마다 가장 높은 값만 남긴다.
	 */
	private static final String ARTICLES_CYPHER = """
			MATCH (a:Article)-[r:COVERS]->(e:Event {nodeId: $eventId})
			WITH a.mysqlArticleId AS articleId,
			     max(coalesce(r.confidence, 0.0)) AS relevance,
			     max(a.publishedAt) AS publishedAt
			RETURN articleId
			ORDER BY relevance DESC, publishedAt DESC, articleId DESC
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jEventArticleRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public List<Long> findArticleIdsByEvent(String eventId) {
		return neo4jClient.query(ARTICLES_CYPHER)
				.bindAll(Map.of("eventId", eventId))
				.fetchAs(Long.class)
				.mappedBy((typeSystem, record) -> record.get("articleId").asLong())
				.all()
				.stream()
				.toList();
	}
}

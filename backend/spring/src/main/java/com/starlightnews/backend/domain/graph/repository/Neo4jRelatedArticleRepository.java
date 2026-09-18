package com.starlightnews.backend.domain.graph.repository;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.graph.support.ArticleCursor;
import com.starlightnews.backend.domain.graph.support.ArticleRelation;
import com.starlightnews.backend.global.neo4j.Neo4jDateTimes;
import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Neo4jClient 기반 관련 기사 조회 구현.
 * 관계 타입은 파라미터화할 수 없으므로 검증된 {@link ArticleRelation} 값에서 문자열로 끼워 넣고,
 * Label 은 labels(n) 포함 여부로 필터한다.
 */
@Repository
public class Neo4jRelatedArticleRepository implements RelatedArticleRepository {

	private static final String EXISTS_NODE_CYPHER = """
			MATCH (n {nodeId: $nodeKey})
			WHERE $label IN labels(n)
			RETURN count(n) > 0 AS present
			""";

	private static final String COUNT_CYPHER = """
			MATCH (a:Article)-[:%s]->(n {nodeId: $nodeKey})
			WHERE $label IN labels(n)
			RETURN count(DISTINCT a.mysqlArticleId) AS total
			""";

	/**
	 * 기사 ID 와 발행 시각. 발행 시각은 정렬·커서 비교 전에 ZONED DATETIME 으로 맞춘다.
	 * 관계 타입 자리({@code %1$s})는 호출 시 채운다.
	 */
	private static final String REFS_CYPHER = """
			MATCH (a:Article)-[:%1$s]->(n {nodeId: $nodeKey})
			WHERE $label IN labels(n)
			WITH DISTINCT a.mysqlArticleId AS articleId, """ + Neo4jDateTimes.normalize("a.publishedAt") + """
			 AS publishedAt
			""";

	private static final String FIRST_PAGE_CYPHER = REFS_CYPHER + """
			RETURN articleId, publishedAt
			ORDER BY publishedAt DESC, articleId DESC
			LIMIT $limit
			""";

	private static final String NEXT_PAGE_CYPHER = REFS_CYPHER + """
			WITH articleId, publishedAt
			WHERE publishedAt < $cursorPublishedAt
			   OR (publishedAt = $cursorPublishedAt AND articleId < $cursorArticleId)
			RETURN articleId, publishedAt
			ORDER BY publishedAt DESC, articleId DESC
			LIMIT $limit
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jRelatedArticleRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public boolean existsNode(ArticleRelation relation, String nodeKey) {
		return neo4jClient.query(EXISTS_NODE_CYPHER)
				.bindAll(Map.of("nodeKey", nodeKey, "label", relation.nodeLabel()))
				.fetchAs(Boolean.class)
				.mappedBy((typeSystem, record) -> record.get("present").asBoolean())
				.one()
				.orElse(false);
	}

	@Override
	public long countRelatedArticles(ArticleRelation relation, String nodeKey) {
		return neo4jClient.query(COUNT_CYPHER.formatted(relation.relationshipType()))
				.bindAll(Map.of("nodeKey", nodeKey, "label", relation.nodeLabel()))
				.fetchAs(Long.class)
				.mappedBy((typeSystem, record) -> record.get("total").asLong())
				.one()
				.orElse(0L);
	}

	@Override
	public List<RelatedArticleRef> findRefs(ArticleRelation relation, String nodeKey, ArticleCursor cursor, int limit) {
		String cypher = (cursor == null ? FIRST_PAGE_CYPHER : NEXT_PAGE_CYPHER)
				.formatted(relation.relationshipType());

		Map<String, Object> params = new HashMap<>();
		params.put("nodeKey", nodeKey);
		params.put("label", relation.nodeLabel());
		params.put("limit", limit);
		if (cursor != null) {
			params.put("cursorPublishedAt", cursor.publishedAt());
			params.put("cursorArticleId", cursor.articleId());
		}

		return neo4jClient.query(cypher)
				.bindAll(params)
				.fetchAs(RelatedArticleRef.class)
				.mappedBy((typeSystem, record) -> new RelatedArticleRef(
						record.get("articleId").asLong(),
						Neo4jDateTimes.toOffsetDateTime(record.get("publishedAt"))))
				.all()
				.stream()
				.toList();
	}
}

package com.starlightnews.backend.domain.article.reconcile;

import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Objects;

import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Article 노드 대사 조회의 Neo4j 구현.
 *
 * <p>mysqlArticleId 에는 유니크 제약(그래프 마이그레이션 V1)이 있어 인덱스를 탄다. 페이지는 OFFSET 이
 * 아니라 마지막 ID 다음부터 읽는다. 노드가 많아져도 뒤 페이지일수록 느려지지 않는다.
 */
@Repository
public class Neo4jGraphArticleRepository implements GraphArticleRepository {

	private static final String FIND_BY_IDS_CYPHER = """
			MATCH (a:Article)
			WHERE a.mysqlArticleId IN $ids
			RETURN a.mysqlArticleId AS mysqlArticleId, a.nodeId AS nodeId
			""";

	private static final String FIND_PAGE_CYPHER = """
			MATCH (a:Article)
			WHERE a.mysqlArticleId > $afterId
			RETURN a.mysqlArticleId AS mysqlArticleId, a.nodeId AS nodeId
			ORDER BY a.mysqlArticleId ASC
			LIMIT $limit
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jGraphArticleRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public List<GraphArticleRef> findByMysqlArticleIds(Collection<Long> mysqlArticleIds) {
		if (mysqlArticleIds.isEmpty()) {
			return List.of();
		}
		return neo4jClient.query(FIND_BY_IDS_CYPHER)
				.bind(List.copyOf(mysqlArticleIds)).to("ids")
				.fetch().all().stream()
				.map(Neo4jGraphArticleRepository::toRef)
				.toList();
	}

	@Override
	public List<GraphArticleRef> findPageAfter(long afterId, int limit) {
		return neo4jClient.query(FIND_PAGE_CYPHER)
				.bind(afterId).to("afterId")
				.bind((long) limit).to("limit")
				.fetch().all().stream()
				.map(Neo4jGraphArticleRepository::toRef)
				.toList();
	}

	private static GraphArticleRef toRef(Map<String, Object> row) {
		long mysqlArticleId = ((Number) row.get("mysqlArticleId")).longValue();
		return new GraphArticleRef(mysqlArticleId, Objects.toString(row.get("nodeId"), null));
	}
}

package com.starlightnews.backend.domain.trend.repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Neo4jClient 기반 트렌드 집계 구현.
 * Article의 primary Event만 세고, Story가 있으면 같은 Story에서 기사 수가 가장 많은 Event 하나만 남긴다.
 * 기사 수가 같으면 가장 최근 기사가 연결된 Event를 우선한다.
 */
@Repository
public class Neo4jTrendAggregationRepository implements TrendAggregationRepository {

	private static final String FIND_TOP_DISTINCT_EVENTS_CYPHER = """
			MATCH (article:Article)-[covers:COVERS]->(event:Event)
			WHERE article.publishedAt >= $from
			  AND article.publishedAt < $snapshotAt
			  AND covers.isPrimary = true
			WITH event,
			     count(DISTINCT article.nodeId) AS articleCount,
			     max(article.publishedAt) AS latestArticleAt

			OPTIONAL MATCH (event)-[:PART_OF]->(story:Story)
			WITH coalesce(story.nodeId, event.nodeId) AS diversityKey,
			     event,
			     articleCount,
			     latestArticleAt
			ORDER BY diversityKey ASC, articleCount DESC, latestArticleAt DESC, event.nodeId ASC

			WITH diversityKey,
			     head(collect({
			       nodeId: event.nodeId,
			       nodeTitle: event.title,
			       articleCount: articleCount,
			       latestArticleAt: latestArticleAt
			     })) AS representative

			WITH representative.nodeId AS nodeId,
			     representative.nodeTitle AS nodeTitle,
			     representative.articleCount AS articleCount,
			     representative.latestArticleAt AS latestArticleAt
			RETURN nodeId, nodeTitle, articleCount
			ORDER BY articleCount DESC, latestArticleAt DESC, nodeId ASC
			LIMIT $limit
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jTrendAggregationRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public List<TrendCandidate> findTopDistinctEvents(
			OffsetDateTime from,
			OffsetDateTime snapshotAt,
			int limit
	) {
		return List.copyOf(neo4jClient.query(FIND_TOP_DISTINCT_EVENTS_CYPHER)
				.bindAll(Map.of(
						"from", from,
						"snapshotAt", snapshotAt,
						"limit", limit))
				.fetchAs(TrendCandidate.class)
				.mappedBy((typeSystem, record) -> new TrendCandidate(
						record.get("nodeId").asString(),
						record.get("nodeTitle").asString(),
						record.get("articleCount").asLong()))
				.all());
	}
}

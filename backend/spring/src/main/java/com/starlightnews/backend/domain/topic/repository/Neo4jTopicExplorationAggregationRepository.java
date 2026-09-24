package com.starlightnews.backend.domain.topic.repository;

import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.global.enums.TopicCode;
import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Neo4jClient 기반 Topic별 탐색 진입 Node 집계 구현.
 * 지원 Topic 전체를 한 번에 집계하고 Topic·Story마다 대표 Event 하나만 남긴다.
 */
@Repository
public class Neo4jTopicExplorationAggregationRepository implements TopicExplorationAggregationRepository {

	private static final String FIND_TOP_DISTINCT_EVENTS_BY_TOPIC_CYPHER = """
			MATCH (article:Article)-[covers:COVERS]->(event:Event)
			MATCH (event)-[:CLASSIFIED_AS]->(topic:Topic)
			WHERE article.publishedAt >= $from
			  AND article.publishedAt < $aggregationAt
			  AND covers.isPrimary = true
			  AND topic.topicCode IN $topicCodes
			WITH topic,
			     event,
			     count(DISTINCT article.nodeId) AS articleCount,
			     max(article.publishedAt) AS latestArticleAt

			OPTIONAL MATCH (event)-[:PART_OF]->(story:Story)
			WITH topic,
			     coalesce(story.nodeId, event.nodeId) AS diversityKey,
			     event,
			     articleCount,
			     latestArticleAt
			ORDER BY topic.topicCode ASC,
			         diversityKey ASC,
			         articleCount DESC,
			         latestArticleAt DESC,
			         event.nodeId ASC

			WITH topic,
			     diversityKey,
			     head(collect({
			       nodeId: event.nodeId,
			       nodeTitle: event.title,
			       articleCount: articleCount,
			       latestArticleAt: latestArticleAt
			     })) AS representative

			WITH topic, representative
			ORDER BY topic.topicCode ASC,
			         representative.articleCount DESC,
			         representative.latestArticleAt DESC,
			         representative.nodeId ASC

			WITH topic, collect(representative)[0..$limitPerTopic] AS entryNodes
			UNWIND entryNodes AS entryNode

			RETURN topic.topicCode AS topicCode,
			       entryNode.nodeId AS nodeId,
			       entryNode.nodeTitle AS nodeTitle,
			       entryNode.articleCount AS articleCount
			ORDER BY topicCode ASC,
			         articleCount DESC,
			         entryNode.latestArticleAt DESC,
			         nodeId ASC
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jTopicExplorationAggregationRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public List<TopicExplorationCandidate> findTopDistinctEventsByTopic(
			OffsetDateTime from,
			OffsetDateTime aggregationAt,
			Collection<TopicCode> topicCodes,
			int limitPerTopic
	) {
		List<String> topicCodeNames = topicCodes.stream()
				.map(TopicCode::name)
				.toList();

		return List.copyOf(neo4jClient.query(FIND_TOP_DISTINCT_EVENTS_BY_TOPIC_CYPHER)
				.bindAll(Map.of(
						"from", from,
						"aggregationAt", aggregationAt,
						"topicCodes", topicCodeNames,
						"limitPerTopic", limitPerTopic))
				.fetchAs(TopicExplorationCandidate.class)
				.mappedBy((typeSystem, record) -> new TopicExplorationCandidate(
						toTopicCode(record.get("topicCode").asString()),
						record.get("nodeId").asString(),
						record.get("nodeTitle").asString(),
						record.get("articleCount").asLong()))
				.all());
	}

	private TopicCode toTopicCode(String value) {
		return TopicCode.from(value)
				.orElseThrow(() -> new IllegalStateException("Neo4j 집계 결과의 Topic 코드가 올바르지 않습니다: " + value));
	}
}

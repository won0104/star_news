package com.starlightnews.backend.domain.user.repository;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.graph.support.ArticleRelation;
import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/** 기간별 그래프를 위해 기사 묶음의 직접 연결 Node를 조회한다. */
@Repository
public class Neo4jPeriodGraphNodeRepository implements PeriodGraphNodeRepository {

	private static final String FIND_CONNECTED_NODES_CYPHER = """
			UNWIND $articleNodeKeys AS articleNodeKey
			MATCH (a:Article {nodeId: articleNodeKey})-[:%s]->(n)
			WHERE $label IN labels(n)
			OPTIONAL MATCH (n)-[classified:CLASSIFIED_AS]->(topic:Topic)
			WITH articleNodeKey, n, topic.topicCode AS topicCode,
			     coalesce(classified.isPrimary, false) AS isPrimary
			ORDER BY isPrimary DESC
			WITH articleNodeKey, n, head(collect(topicCode)) AS topicCode
			RETURN articleNodeKey, n.nodeId AS nodeKey,
			       coalesce(n[$titleProp], n.nodeId) AS label, topicCode
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jPeriodGraphNodeRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public List<PeriodGraphNodeRef> findConnectedNodes(Collection<String> articleNodeKeys) {
		if (articleNodeKeys.isEmpty()) {
			return List.of();
		}

		List<PeriodGraphNodeRef> refs = new ArrayList<>();
		for (ArticleRelation relation : ArticleRelation.values()) {
			refs.addAll(neo4jClient.query(FIND_CONNECTED_NODES_CYPHER.formatted(relation.relationshipType()))
					.bindAll(Map.of(
							"articleNodeKeys", List.copyOf(articleNodeKeys),
							"label", relation.nodeLabel(),
							"titleProp", relation.nodeType().titleProperty()))
					.fetchAs(PeriodGraphNodeRef.class)
					.mappedBy((typeSystem, record) -> new PeriodGraphNodeRef(
							record.get("articleNodeKey").asString(),
							relation.nodeType(),
							record.get("nodeKey").asString(),
							record.get("label").asString(),
							record.get("topicCode").isNull() ? null : record.get("topicCode").asString()))
					.all());
		}
		return refs;
	}
}

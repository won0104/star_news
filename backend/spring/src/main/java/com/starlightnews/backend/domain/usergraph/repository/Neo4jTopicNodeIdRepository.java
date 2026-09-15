package com.starlightnews.backend.domain.usergraph.repository;

import java.util.HashMap;
import java.util.Map;

import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Neo4j 의 고정 Topic 노드에서 코드와 nodeId 를 읽는다.
 *
 * <p>Topic 은 그래프 마이그레이션이 심어 두는 7개로 고정이라 전건을 한 번에 가져온다.
 */
@Repository
public class Neo4jTopicNodeIdRepository implements TopicNodeIdRepository {

	private static final String FIND_ALL_CYPHER = """
			MATCH (t:Topic)
			WHERE t.topicCode IS NOT NULL AND t.nodeId IS NOT NULL
			RETURN t.topicCode AS topicCode, t.nodeId AS nodeId
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jTopicNodeIdRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public Map<String, String> findAllTopicNodeIds() {
		Map<String, String> nodeIdsByCode = new HashMap<>();
		neo4jClient.query(FIND_ALL_CYPHER)
				.fetch()
				.all()
				.forEach(row -> nodeIdsByCode.put(
						String.valueOf(row.get("topicCode")),
						String.valueOf(row.get("nodeId"))));
		return Map.copyOf(nodeIdsByCode);
	}
}

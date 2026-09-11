package com.starlightnews.backend.domain.user.repository;

import java.util.Map;
import java.util.Optional;

import com.starlightnews.backend.global.enums.NodeType;
import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Neo4jClient 기반 개인 Node 스냅샷 조회.
 * Label 은 labels(n) 포함 여부로 필터하고, 표시 이름은 유형별 이름 속성(n[$titleProp])으로 뽑는다.
 * 대표 Topic 은 CLASSIFIED_AS 관계 중 isPrimary 우선으로 하나만 취하며, 관계가 없으면 null 이다(ENTITY·STATEMENT).
 */
@Repository
public class Neo4jNodeSnapshotRepository implements NodeSnapshotRepository {

	private static final String FIND_SNAPSHOT_CYPHER = """
			MATCH (n {nodeId: $nodeKey})
			WHERE $label IN labels(n)
			OPTIONAL MATCH (n)-[classified:CLASSIFIED_AS]->(topic:Topic)
			WITH n, topic.topicCode AS topicCode, coalesce(classified.isPrimary, false) AS isPrimary
			ORDER BY isPrimary DESC
			RETURN coalesce(n[$titleProp], $nodeKey) AS label, head(collect(topicCode)) AS topicCode
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jNodeSnapshotRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public Optional<NodeSnapshot> findSnapshot(NodeType nodeType, String nodeKey) {
		return neo4jClient.query(FIND_SNAPSHOT_CYPHER)
				.bindAll(Map.of(
						"nodeKey", nodeKey,
						"label", nodeType.label(),
						"titleProp", nodeType.titleProperty()))
				.fetchAs(NodeSnapshot.class)
				.mappedBy((typeSystem, record) -> new NodeSnapshot(
						record.get("label").asString(),
						record.get("topicCode").isNull() ? null : record.get("topicCode").asString()))
				.one();
	}
}

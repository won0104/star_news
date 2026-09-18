package com.starlightnews.backend.domain.graph.repository;

import java.util.Map;
import java.util.Optional;

import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.neo4j.Neo4jDateTimes;
import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Neo4jClient 기반 그래프 Node 조회 구현.
 * Label 은 파라미터화할 수 없으므로 labels(n) 포함 여부로 필터하고, 표시 속성명은 동적 속성 접근(n[$prop])으로 뽑는다.
 * 없는 속성명("")은 Cypher 상 null 로 평가된다.
 */
@Repository
public class Neo4jGraphNodeRepository implements GraphNodeRepository {

	private static final String FIND_NODE_CYPHER = """
			MATCH (n {nodeId: $nodeKey})
			WHERE $label IN labels(n)
			RETURN n[$titleProp] AS title, n[$typeProp] AS type, n[$timeProp] AS time
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jGraphNodeRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public Optional<GraphNodeRecord> findNode(NodeType nodeType, String nodeKey) {
		Map<String, Object> params = Map.of(
				"nodeKey", nodeKey,
				"label", nodeType.label(),
				"titleProp", nodeType.titleProperty(),
				"typeProp", orEmpty(nodeType.typeProperty()),
				"timeProp", orEmpty(nodeType.timeProperty()));

		return neo4jClient.query(FIND_NODE_CYPHER)
				.bindAll(params)
				.fetchAs(GraphNodeRecord.class)
				.mappedBy((typeSystem, record) -> new GraphNodeRecord(
						record.get("title").isNull() ? null : record.get("title").asString(),
						record.get("type").isNull() ? null : record.get("type").asString(),
						Neo4jDateTimes.toOffsetDateTime(record.get("time"))))
				.one();
	}

	private static String orEmpty(String property) {
		return property == null ? "" : property;
	}
}

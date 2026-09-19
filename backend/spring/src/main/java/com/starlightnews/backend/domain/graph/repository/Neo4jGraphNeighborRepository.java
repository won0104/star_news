package com.starlightnews.backend.domain.graph.repository;

import java.util.Collection;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.global.enums.NodeType;
import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Neo4jClient 기반 주변 그래프 조회 구현.
 * 가변 길이 경로의 상한(depth)은 파라미터화할 수 없으므로 1~3 으로 검증한 뒤 Cypher 에 정수로 끼워 넣고,
 * Label 은 labels() 포함 여부로 필터한다. 표시 Node 유형은 EVENT·ENTITY·STATEMENT·TIME 으로 한정한다.

 */
@Repository
public class Neo4jGraphNeighborRepository implements GraphNeighborRepository {

	private static final int MIN_DEPTH = 1;
	private static final int MAX_DEPTH = 3;

	/**
	 * 중심 Node 에서 depth Hop 이내 주변 Node 를 조회한다.
	 * - 경로의 마지막·중간 Node 는 모두 표시 유형(Event·Entity·Statement·Time)이어야 한다.
	 * - neighborScore = 각 연결 경로의 (관계 가중치 곱 / Hop 수) 중 최댓값.
	 * - 관계 가중치는 KG 추출 모델이 준 confidence 다. 표시 Node 사이 관계(ACTOR·TARGET·PLACE·OCCURRED_ON)에는
	 *   relevance·weight 가 없다. confidence 가 비어 있으면 0.5 로 본다.
	 */
	private static final String NEIGHBORS_CYPHER = """
			MATCH path = (c)-[*%d..%d]-(n)
			WHERE $centerLabel IN labels(c) AND c.nodeId = $centerKey
			  AND n <> c
			  AND (n:Event OR n:Entity OR n:Statement OR n:Time)
			  AND all(x IN nodes(path)[1..-1] WHERE x:Event OR x:Entity OR x:Statement OR x:Time)
			WITH n, reduce(s = 1.0, r IN relationships(path) |
			              s * coalesce(r.confidence, 0.5)) / length(path) AS pathScore
			WITH n, max(pathScore) AS neighborScore
			WITH n, neighborScore,
			     [lbl IN labels(n) WHERE lbl IN ['Event', 'Entity', 'Statement', 'Time']][0] AS primaryLabel
			WITH n, neighborScore,
			     CASE primaryLabel
			         WHEN 'Event' THEN 'EVENT'
			         WHEN 'Entity' THEN 'ENTITY'
			         WHEN 'Statement' THEN 'STATEMENT'
			         WHEN 'Time' THEN 'TIME'
			     END AS nodeType,
			     CASE primaryLabel
			         WHEN 'Event' THEN n.title
			         WHEN 'Entity' THEN n.canonicalName
			         WHEN 'Statement' THEN n.text
			         WHEN 'Time' THEN n.value
			     END AS label
			RETURN nodeType, n.nodeId AS nodeKey, label, neighborScore
			ORDER BY neighborScore DESC, nodeType ASC, nodeKey ASC
			LIMIT $fetchCap
			""";

	private static final String EDGES_CYPHER = """
			MATCH (a)-[r]->(b)
			WHERE a.nodeId IN $nodeKeys AND b.nodeId IN $nodeKeys AND a.nodeId <> b.nodeId
			RETURN a.nodeId AS sourceNodeKey, b.nodeId AS targetNodeKey, type(r) AS edgeType,
			       coalesce(r.confidence, 0.5) AS weight
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jGraphNeighborRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public List<NeighborNode> findNeighbors(NodeType centerType, String centerKey, int depth, int fetchCap) {
		if (depth < MIN_DEPTH || depth > MAX_DEPTH) {
			throw new IllegalArgumentException("depth must be between %d and %d: %d"
					.formatted(MIN_DEPTH, MAX_DEPTH, depth));
		}

		return neo4jClient.query(NEIGHBORS_CYPHER.formatted(MIN_DEPTH, depth))
				.bindAll(Map.of(
						"centerLabel", centerType.label(),
						"centerKey", centerKey,
						"fetchCap", fetchCap))
				.fetchAs(NeighborNode.class)
				.mappedBy((typeSystem, record) -> new NeighborNode(
						record.get("nodeType").asString(),
						record.get("nodeKey").asString(),
						record.get("label").isNull() ? null : record.get("label").asString(),
						record.get("neighborScore").asDouble()))
				.all()
				.stream()
				.toList();
	}

	@Override
	public List<NeighborEdge> findEdges(Collection<String> nodeKeys) {
		if (nodeKeys.isEmpty()) {
			return List.of();
		}

		return neo4jClient.query(EDGES_CYPHER)
				.bindAll(Map.of("nodeKeys", List.copyOf(nodeKeys)))
				.fetchAs(NeighborEdge.class)
				.mappedBy((typeSystem, record) -> new NeighborEdge(
						record.get("sourceNodeKey").asString(),
						record.get("targetNodeKey").asString(),
						record.get("edgeType").asString(),
						record.get("weight").asDouble()))
				.all()
				.stream()
				.toList();
	}
}

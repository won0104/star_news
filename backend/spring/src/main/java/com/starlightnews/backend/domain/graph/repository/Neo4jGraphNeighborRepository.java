package com.starlightnews.backend.domain.graph.repository;

import java.util.Collection;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.graph.GraphNeighborProperties;
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
	 *
	 * <p>경로의 마지막·중간 Node 는 모두 표시 유형(Event·Entity·Statement·Time)이어야 한다.
	 *
	 * <p>neighborScore 는 연결 경로마다 아래를 구해 그중 최댓값을 쓴다.
	 * <pre>
	 * (관계 가중치 곱 / Hop 수) / 허브 감점 × 기사 수 보정 × 최신성
	 * </pre>
	 *
	 * <p><b>관계 가중치</b>는 KG 추출 모델이 준 confidence 에 관계 종류별 가중치를 곱한 값이다. 표시
	 * Node 사이 관계에는 relevance·weight 가 없어 confidence 만 온다. 장소·시점 관계는 인물·기관보다
	 * 사건을 덜 설명하므로 낮춘다. confidence 가 비어 있으면 0.5 로 본다.
	 *
	 * <p><b>허브 감점</b>은 연결 수가 기준을 넘는 만큼만 깎는다. 기사 그래프에는 "미국"처럼 수천 갈래로
	 * 이어진 Entity 가 있어, 그대로 두면 어느 사건에서 출발해도 이런 Node 가 앞자리를 차지한다.
	 * 단순히 연결 수로 나누면 반대로 연결이 두셋뿐인 잡음 Node 가 올라와, 기준 위쪽만 깎는다.
	 *
	 * <p><b>기사 수 보정</b>은 뒷받침하는 기사가 많은 Node 를 올린다. confidence 가 사실상 상수라
	 * 이것이 없으면 2홉 Node 가 전부 동점이 되고, 그다음 기준인 nodeKey(UUID) 순서는 무작위나 같다.
	 *
	 * <p><b>최신성</b>은 마지막으로 다뤄진 기사가 오래될수록 점수를 반감기로 줄인다. 뉴스 탐색이라
	 * 반년 전 사건과 어제 사건이 같은 자리를 다투면 안 된다. 기사가 붙지 않는 Time Node 처럼 시각을
	 * 알 수 없으면 줄이지 않는다.
	 */
	private static final String NEIGHBORS_CYPHER = """
			MATCH path = (c)-[*%d..%d]-(n)
			WHERE $centerLabel IN labels(c) AND c.nodeId = $centerKey
			  AND n <> c
			  AND (n:Event OR n:Entity OR n:Statement OR n:Time)
			  // 허브는 결과에는 남기되 2홉 경유지로는 쓰지 않는다. 그대로 두면 "미국" 하나를 거쳐
			  // 아무 사건으로나 이어져, 어느 사건에서 출발해도 같은 이웃이 나온다.
			  AND all(x IN nodes(path)[1..-1] WHERE
			        (x:Event OR x:Entity OR x:Statement OR x:Time)
			        AND count { (x)--() } <= $traverseThreshold)
			WITH n, reduce(s = 1.0, r IN relationships(path) |
			              s * coalesce(r.confidence, 0.5) *
			              CASE type(r)
			                  WHEN 'PLACE' THEN $placeWeight
			                  WHEN 'OCCURRED_ON' THEN $timeWeight
			                  ELSE 1.0
			              END) / length(path) AS pathScore
			WITH n, max(pathScore) AS pathBest
			CALL {
			    WITH n
			    MATCH (a:Article)-[:COVERS|MENTIONS|CONTAINS_STATEMENT]->(n)
			    RETURN count(a) AS articleCount, max(a.publishedAt) AS latestArticleAt
			}
			WITH n, pathBest, articleCount, count { (n)--() } AS degree,
			     CASE WHEN latestArticleAt IS NULL THEN 0.0
			          ELSE toFloat(duration.inSeconds(latestArticleAt, datetime()).seconds) / 86400.0
			     END AS daysSinceLatest
			WITH n,
			     pathBest
			       / (1 + log(1 + toFloat(CASE WHEN degree > $hubThreshold
			                                   THEN degree - $hubThreshold ELSE 0 END) / $hubThreshold))
			       * (1 + $supportWeight * log(1 + articleCount))
			       * exp(-log(2) * (CASE WHEN daysSinceLatest > 0 THEN daysSinceLatest ELSE 0.0 END)
			             / $recencyHalfLifeDays) AS neighborScore
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
	private final GraphNeighborProperties properties;

	public Neo4jGraphNeighborRepository(Neo4jClient neo4jClient, GraphNeighborProperties properties) {
		this.neo4jClient = neo4jClient;
		this.properties = properties;
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
						"fetchCap", fetchCap,
						"hubThreshold", properties.hubThreshold(),
						"traverseThreshold", properties.traverseThreshold(),
						"placeWeight", properties.placeWeight(),
						"timeWeight", properties.timeWeight(),
						"supportWeight", properties.supportWeight(),
						"recencyHalfLifeDays", properties.recencyHalfLifeDays()))
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

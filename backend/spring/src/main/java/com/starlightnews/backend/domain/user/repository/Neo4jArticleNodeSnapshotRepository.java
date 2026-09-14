package com.starlightnews.backend.domain.user.repository;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.graph.support.ArticleRelation;
import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * Neo4jClient 기반 기사 연결 Node 스냅샷 조회.
 * 관계 타입은 파라미터화할 수 없으므로 검증된 {@link ArticleRelation} 값에서 문자열로 끼워 넣고,
 * Label 은 labels(n) 포함 여부로 필터한다. 대표 Topic 은 CLASSIFIED_AS 중 isPrimary 우선으로 하나만 취한다.
 *
 * <p>관계 유형마다 Label 과 표시 이름 속성이 달라 {@link ArticleRelation} 개수(3)만큼 질의한다.
 * 연결 Node 수 N 에 비례하지 않는 고정 횟수이며, Node 마다 스냅샷을 따로 조회하면 N 번이 된다.
 */
@Repository
public class Neo4jArticleNodeSnapshotRepository implements ArticleNodeSnapshotRepository {

	private static final String FIND_CONNECTED_NODES_CYPHER = """
			MATCH (a:Article {nodeId: $articleNodeKey})-[:%s]->(n)
			WHERE $label IN labels(n)
			OPTIONAL MATCH (n)-[classified:CLASSIFIED_AS]->(topic:Topic)
			WITH n, topic.topicCode AS topicCode, coalesce(classified.isPrimary, false) AS isPrimary
			ORDER BY isPrimary DESC
			WITH n, head(collect(topicCode)) AS topicCode
			RETURN n.nodeId AS nodeKey, coalesce(n[$titleProp], n.nodeId) AS label, topicCode
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jArticleNodeSnapshotRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public List<ArticleNodeSnapshot> findConnectedNodes(String articleNodeKey) {
		List<ArticleNodeSnapshot> snapshots = new ArrayList<>();
		for (ArticleRelation relation : ArticleRelation.values()) {
			snapshots.addAll(findByRelation(relation, articleNodeKey));
		}
		return snapshots;
	}

	private List<ArticleNodeSnapshot> findByRelation(ArticleRelation relation, String articleNodeKey) {
		return neo4jClient.query(FIND_CONNECTED_NODES_CYPHER.formatted(relation.relationshipType()))
				.bindAll(Map.of(
						"articleNodeKey", articleNodeKey,
						"label", relation.nodeLabel(),
						"titleProp", relation.nodeType().titleProperty()))
				.fetchAs(ArticleNodeSnapshot.class)
				.mappedBy((typeSystem, record) -> new ArticleNodeSnapshot(
						relation.nodeType(),
						record.get("nodeKey").asString(),
						record.get("label").asString(),
						record.get("topicCode").isNull() ? null : record.get("topicCode").asString()))
				.all()
				.stream()
				.toList();
	}
}

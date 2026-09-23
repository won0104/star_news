package com.starlightnews.backend.domain.demo.repository;

import java.util.List;
import java.util.Map;

import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * 기사 서브그래프 조회의 Neo4j 구현.
 *
 * <p>노드 종류마다 이름을 담는 속성이 다르다(Event·Story 는 title, Entity 는 canonicalName,
 * Statement 는 text, Topic 은 nameKo, Time 은 value). 화면은 그 차이를 알 필요가 없으므로 여기서
 * 하나의 label 로 맞춰서 준다.
 *
 * <p>라벨도 마찬가지다. Entity 는 Person·Organization 같은 두 번째 라벨을 함께 갖는데,
 * {@code labels(n)[0]} 을 쓰면 어느 것이 나올지 보장되지 않는다. 아는 라벨만 걸러 쓴다.
 */
@Repository
public class Neo4jDemoGraphRepository implements DemoGraphRepository {

	/** 기사가 직접 거는 관계. */
	private static final List<String> ARTICLE_RELATIONS =
			List.of("COVERS", "MENTIONS", "CONTAINS_STATEMENT", "CLASSIFIED_AS", "PUBLISHED_BY");

	/**
	 * 대표 사건만 볼 때 기사가 거는 관계.
	 *
	 * <p>스치듯 언급된 개체(MENTIONS)와 본문에서 뽑은 발언(CONTAINS_STATEMENT)을 뺀다. 기사 한
	 * 건에서 이 둘이 40개 넘게 나와 화면을 채운다.
	 */
	private static final List<String> PRIMARY_ARTICLE_RELATIONS =
			List.of("COVERS", "CLASSIFIED_AS", "PUBLISHED_BY");

	/** 사건이 거는 관계. */
	private static final List<String> EVENT_RELATIONS =
			List.of("ACTOR", "TARGET", "PLACE", "CLASSIFIED_AS", "OCCURRED_ON", "PART_OF");

	private static final String NODE_TYPE = """
			[label IN labels(%1$s)
			 WHERE label IN ['Article','Event','Entity','Statement','Topic','Time','Story']][0]
			""";

	private static final String NODE_LABEL = """
			coalesce(%1$s.title, %1$s.canonicalName, %1$s.text, %1$s.nameKo,
			         toString(%1$s.value), %1$s.nodeId)
			""";

	/**
	 * 기사에서 두 홉까지를 간선 단위로 읽는다.
	 *
	 * <p>{@code primaryOnly} 면 대표로 다루는 사건(COVERS.isPrimary)만 남기고, 그 사건에서만
	 * 다음 홉으로 뻗는다.
	 */
	private static final String FIND_ARTICLE_SUBGRAPH_CYPHER = """
			MATCH (article:Article {nodeId: $articleNodeKey})
			CALL {
			  WITH article
			  MATCH (article)-[link]->(target)
			  WHERE type(link) IN $articleRelations
			    AND (type(link) <> 'COVERS' OR NOT $primaryOnly OR coalesce(link.isPrimary, false))
			  RETURN article AS source, link, target
			UNION
			  WITH article
			  MATCH (article)-[covers:COVERS]->(event:Event)-[link]->(target)
			  WHERE type(link) IN $eventRelations
			    AND (NOT $primaryOnly OR coalesce(covers.isPrimary, false))
			  RETURN event AS source, link, target
			}
			RETURN source.nodeId AS fromKey,
			       %1$s AS fromType,
			       %2$s AS fromLabel,
			       source.entityType AS fromSubType,
			       type(link) AS relation,
			       coalesce(link.isPrimary, false) AS isPrimary,
			       target.nodeId AS toKey,
			       %3$s AS toType,
			       %4$s AS toLabel,
			       target.entityType AS toSubType
			"""
			.formatted(
					NODE_TYPE.formatted("source"),
					NODE_LABEL.formatted("source"),
					NODE_TYPE.formatted("target"),
					NODE_LABEL.formatted("target"));

	private final Neo4jClient neo4jClient;

	public Neo4jDemoGraphRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public List<DemoGraphRow> findArticleSubgraph(String articleNodeKey, boolean primaryOnly) {
		return List.copyOf(neo4jClient.query(FIND_ARTICLE_SUBGRAPH_CYPHER)
				.bindAll(Map.of(
						"articleNodeKey", articleNodeKey,
						"articleRelations", primaryOnly ? PRIMARY_ARTICLE_RELATIONS : ARTICLE_RELATIONS,
						"eventRelations", EVENT_RELATIONS,
						"primaryOnly", primaryOnly))
				.fetchAs(DemoGraphRow.class)
				.mappedBy((typeSystem, record) -> new DemoGraphRow(
						record.get("fromKey").asString(),
						record.get("fromType").asString(null),
						record.get("fromLabel").asString(null),
						record.get("fromSubType").asString(null),
						record.get("relation").asString(),
						record.get("isPrimary").asBoolean(false),
						record.get("toKey").asString(),
						record.get("toType").asString(null),
						record.get("toLabel").asString(null),
						record.get("toSubType").asString(null)))
				.all());
	}
}

package com.starlightnews.backend.domain.search.repository;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.search.support.NormalizedSearchQuery;
import com.starlightnews.backend.domain.search.support.SearchCursor;
import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.stereotype.Repository;

/**
 * 기존 Full-text index로 후보를 찾고 원본 표시 속성만으로 순위와 페이지를 계산한다.
 * Lucene property 범위를 지정해 Event.aliases와 Entity.aliases는 후보 조회에서도 제외한다.
 */
@Repository
public class Neo4jSearchRepository implements SearchRepository {

	private static final String SEARCH_CYPHER = """
			CALL () {
			    CALL db.index.fulltext.queryNodes('event_fulltext', $eventFulltextQuery) YIELD node
			    WHERE node:Event
			    RETURN node.nodeId AS nodeKey, 'EVENT' AS nodeType, node.title AS label, 0 AS nodeTypeOrder
			    UNION ALL
			    CALL db.index.fulltext.queryNodes('entity_fulltext', $entityFulltextQuery) YIELD node
			    WHERE node:Entity
			    RETURN node.nodeId AS nodeKey, 'ENTITY' AS nodeType, node.canonicalName AS label, 1 AS nodeTypeOrder
			    UNION ALL
			    CALL db.index.fulltext.queryNodes('statement_text_fulltext', $statementFulltextQuery) YIELD node
			    WHERE node:Statement
			    RETURN node.nodeId AS nodeKey, 'STATEMENT' AS nodeType, node.text AS label, 2 AS nodeTypeOrder
			}
			WITH nodeKey, nodeType, label, nodeTypeOrder, toLower(trim(label)) AS comparableLabel
			WHERE nodeKey IS NOT NULL AND label IS NOT NULL
			WITH nodeKey, nodeType, label, nodeTypeOrder, comparableLabel,
			     reduce(count = 0, token IN $tokens |
			         count + CASE WHEN comparableLabel CONTAINS token THEN 1 ELSE 0 END) AS matchedTokenCount
			WHERE matchedTokenCount > 0
			WITH nodeKey, nodeType, label, nodeTypeOrder, matchedTokenCount,
			     CASE
			         WHEN comparableLabel = $exactPhrase THEN 3
			         WHEN matchedTokenCount = size($tokens) THEN 2
			         ELSE 1
			     END AS matchTier
			WHERE NOT $hasCursor
			   OR matchTier < $cursorMatchTier
			   OR (matchTier = $cursorMatchTier AND matchedTokenCount < $cursorMatchedTokenCount)
			   OR (matchTier = $cursorMatchTier AND matchedTokenCount = $cursorMatchedTokenCount
			       AND nodeTypeOrder > $cursorNodeTypeOrder)
			   OR (matchTier = $cursorMatchTier AND matchedTokenCount = $cursorMatchedTokenCount
			       AND nodeTypeOrder = $cursorNodeTypeOrder AND nodeKey > $cursorNodeKey)
			RETURN nodeType, nodeKey, label, matchTier, matchedTokenCount, nodeTypeOrder
			ORDER BY matchTier DESC, matchedTokenCount DESC, nodeTypeOrder ASC, nodeKey ASC
			LIMIT $limit
			""";

	private final Neo4jClient neo4jClient;

	public Neo4jSearchRepository(Neo4jClient neo4jClient) {
		this.neo4jClient = neo4jClient;
	}

	@Override
	public List<SearchNode> search(NormalizedSearchQuery query, SearchCursor cursor, int limit) {
		Map<String, Object> parameters = new HashMap<>();
		parameters.put("eventFulltextQuery", propertyQuery("title", query.fulltextQuery()));
		parameters.put("entityFulltextQuery", propertyQuery("canonicalName", query.fulltextQuery()));
		parameters.put("statementFulltextQuery", propertyQuery("text", query.fulltextQuery()));
		parameters.put("exactPhrase", query.exactPhrase());
		parameters.put("tokens", query.tokens());
		parameters.put("limit", limit);
		parameters.put("hasCursor", cursor != null);
		parameters.put("cursorMatchTier", cursor == null ? 0 : cursor.matchTier());
		parameters.put("cursorMatchedTokenCount", cursor == null ? 0 : cursor.matchedTokenCount());
		parameters.put("cursorNodeTypeOrder", cursor == null ? 0 : cursor.nodeTypeOrder());
		parameters.put("cursorNodeKey", cursor == null ? "" : cursor.nodeKey());

		return neo4jClient.query(SEARCH_CYPHER)
				.bindAll(parameters)
				.fetchAs(SearchNode.class)
				.mappedBy((typeSystem, record) -> new SearchNode(
						record.get("nodeType").asString(),
						record.get("nodeKey").asString(),
						record.get("label").asString(),
						record.get("matchTier").asInt(),
						record.get("matchedTokenCount").asInt(),
						record.get("nodeTypeOrder").asInt()))
				.all()
				.stream()
				.toList();
	}

	private static String propertyQuery(String property, String fulltextQuery) {
		return property + ":(" + fulltextQuery + ")";
	}
}

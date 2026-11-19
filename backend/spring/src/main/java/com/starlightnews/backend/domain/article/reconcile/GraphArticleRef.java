package com.starlightnews.backend.domain.article.reconcile;

/**
 * Neo4j Article 노드 한 개. FastAPI 가 MySQL articleId 를 자연키(mysqlArticleId)로 MERGE 한다.
 *
 * @param mysqlArticleId MySQL articles.article_id
 * @param nodeId         FastAPI 가 만든 노드 ID. MySQL articles.node_id 와 같아야 한다
 */
public record GraphArticleRef(long mysqlArticleId, String nodeId) {
}

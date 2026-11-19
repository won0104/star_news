package com.starlightnews.backend.domain.article.reconcile;

import java.util.Collection;
import java.util.List;

/**
 * 대사에 필요한 만큼만 Neo4j Article 노드를 읽는다. 쓰기는 하지 않는다(Neo4j 의 쓰기 주체는 FastAPI).
 */
public interface GraphArticleRepository {

	/** 주어진 MySQL articleId 에 해당하는 Article 노드. 없는 ID 는 결과에 빠진다. */
	List<GraphArticleRef> findByMysqlArticleIds(Collection<Long> mysqlArticleIds);

	/** mysqlArticleId 가 {@code afterId} 보다 큰 Article 노드를 ID 오름차순으로 {@code limit} 건. */
	List<GraphArticleRef> findPageAfter(long afterId, int limit);
}

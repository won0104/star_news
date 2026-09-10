package com.starlightnews.backend.domain.graph.repository;

import java.util.List;

import com.starlightnews.backend.domain.graph.support.ArticleCursor;
import com.starlightnews.backend.domain.graph.support.ArticleRelation;

/**
 * Node 와 연결된 Article 조회 (Neo4j, 읽기 전용). articleId(mysqlArticleId) 와 정렬 키만 다룬다.
 */
public interface RelatedArticleRepository {

	/** 해당 Label 의 Node 가 존재하는지 확인한다. */
	boolean existsNode(ArticleRelation relation, String nodeKey);

	/** 중복 제거한 전체 관련 기사 수. */
	long countRelatedArticles(ArticleRelation relation, String nodeKey);

	/**
	 * publishedAt DESC, articleId DESC 순으로 관련 기사 키를 조회한다.
	 * cursor 가 null 이면 첫 페이지, 아니면 cursor 위치 다음부터. 최대 limit 개.
	 */
	List<RelatedArticleRef> findRefs(ArticleRelation relation, String nodeKey, ArticleCursor cursor, int limit);
}

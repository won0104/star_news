package com.starlightnews.backend.domain.user.repository;

import java.util.List;

import com.starlightnews.backend.domain.graph.support.ArticleRelation;

/**
 * 개인 그래프 Node 와 관련된 기사 후보 조회 (Neo4j, 읽기 전용).
 * `-28`과 달리 정렬·페이지네이션은 하지 않는다 — 실제 정렬(내가 읽은 시각 기준)과 커서는
 * MySQL article_reads 가 담당하고, 여기서는 그 Node 와 관련된 기사 id 후보 전체만 가져온다.
 */
public interface PersonalNodeArticleRepository {

	/** 해당 Node 와 관련된 기사의 MySQL articleId 전체를 중복 없이 반환한다. 정렬 순서는 보장하지 않는다. */
	List<Long> findRelatedArticleIds(ArticleRelation relation, String nodeKey);
}

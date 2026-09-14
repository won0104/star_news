package com.starlightnews.backend.domain.article.repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.article.domain.Article;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 기사 조회 (읽기 전용).
 */
public interface ArticleRepository extends Repository<Article, Long> {

	/** 해당 기사가 존재하는지 확인한다. (열람 기록 저장 전 대상 검증용) */
	boolean existsById(Long articleId);

	/** 기사의 Neo4j 참조 한 행. */
	interface ArticleGraphRef {
		/**
		 * 기사 PK. nodeId 만 뽑으면 분석 전 기사는 행 전체가 null 이라
		 * Spring Data 가 빈 Optional 을 돌려줘 "기사 없음"과 구분되지 않는다.
		 */
		Long getArticleId();

		/** Neo4j Article Node 의 nodeId. AI 분석 전이면 null. */
		String getNodeId();
	}

	/**
	 * 기사의 Neo4j 참조만 조회한다. (열람 기록 저장 시 연결 Node 를 찾기 위한 진입점)
	 * 빈 Optional 은 기사 자체가 없다는 뜻이고, nodeId 가 null 이면 기사는 있으나 아직 분석 전이다.
	 */
	Optional<ArticleGraphRef> findGraphRefByArticleId(Long articleId);

	/** articleId 목록으로 기사를 언론사와 함께(JOIN FETCH) 조회한다. */
	@Query("SELECT a FROM Article a JOIN FETCH a.organization WHERE a.articleId IN :articleIds")
	List<Article> findAllWithOrganizationByArticleIdIn(@Param("articleIds") Collection<Long> articleIds);
}

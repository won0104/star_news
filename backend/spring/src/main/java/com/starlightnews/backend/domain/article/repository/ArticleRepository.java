package com.starlightnews.backend.domain.article.repository;

import java.util.Collection;
import java.util.List;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 기사 조회 (읽기 전용).
 */
public interface ArticleRepository extends Repository<Article, Long> {

	/** articleId 목록으로 기사를 언론사와 함께(JOIN FETCH) 조회한다. */
	@Query("SELECT a FROM Article a JOIN FETCH a.organization WHERE a.articleId IN :articleIds")
	List<Article> findAllWithOrganizationByArticleIdIn(@Param("articleIds") Collection<Long> articleIds);

	/** 주어진 ID 중 지정한 분석 상태의 기사 ID만 반환한다. */
	@Query("SELECT a.articleId FROM Article a "
			+ "WHERE a.articleId IN :articleIds AND a.analysisStatus = :analysisStatus")
	List<Long> findArticleIdsByIdInAndAnalysisStatus(
			@Param("articleIds") Collection<Long> articleIds,
			@Param("analysisStatus") AnalysisStatus analysisStatus);
}

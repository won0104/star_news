package com.starlightnews.backend.domain.article.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 기사 조회·저장. (articles)
 */
public interface ArticleRepository extends Repository<Article, Long> {

	/** 해당 기사가 존재하는지 확인한다. (열람 기록 저장 전 대상 검증용) */
	boolean existsById(Long articleId);

	/**
	 * 수집한 기사를 저장한다. 같은 기사를 다시 수집했으면(url_hash UNIQUE 충돌) 아무것도 바꾸지 않는다.
	 *
	 * <p>이미 저장된 기사는 건너뛴다. 본문 갱신은 재분석 여부까지 함께 정해야 해서 이 단계의 일이 아니다.
	 *
	 * <p>JPA save 로 저장하면 중복 시 제약 위반이 commit 시점에 나서 잡을 수 없고, 한 건 때문에
	 * 회차 전체가 롤백된다. 단일 Upsert 문장이면 중복이 그냥 무시된다.
	 *
	 * <p>analysis_status 는 컬럼 기본값에 맡기지 않고 명시한다. 기본값은 실제 스키마에만 있고
	 * 엔티티에서 생성되는 테스트 DB 에는 없어서, 맡겨두면 두 환경의 동작이 갈린다.
	 * INSERT 문에서 생략한 summary_status·content_updated_at 은 실제 스키마의 기본값을 쓴다.
	 */
	@Modifying
	@Query(value = "INSERT INTO articles "
			+ "(organization_id, title, url, url_hash, published_at, source_category, content, "
			+ " content_type, analysis_status) "
			+ "VALUES (:organizationId, :title, :url, :urlHash, :publishedAt, :sourceCategory, "
			+ " :content, :contentType, :analysisStatus) "
			+ "ON DUPLICATE KEY UPDATE article_id = article_id",
			nativeQuery = true)
	void insertIfAbsent(@Param("organizationId") Long organizationId,
			@Param("title") String title,
			@Param("url") String url,
			@Param("urlHash") byte[] urlHash,
			@Param("publishedAt") LocalDateTime publishedAt,
			@Param("sourceCategory") String sourceCategory,
			@Param("content") String content,
			@Param("contentType") String contentType,
			@Param("analysisStatus") String analysisStatus);

	/** url 해시로 기사 ID 를 찾는다. 저장 여부 확인용. */
	@Query("SELECT a.articleId FROM Article a WHERE a.urlHash = :urlHash")
	Optional<Long> findIdByUrlHash(@Param("urlHash") byte[] urlHash);

	/** 지정한 분석 상태의 기사 상세와 언론사를 한 번에 조회한다. */
	@Query("SELECT a FROM Article a JOIN FETCH a.organization "
			+ "WHERE a.articleId = :articleId AND a.analysisStatus = :analysisStatus")
	Optional<Article> findDetailByArticleId(
			@Param("articleId") Long articleId,
			@Param("analysisStatus") AnalysisStatus analysisStatus);

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

	/** 주어진 ID 중 지정한 분석 상태의 기사 ID만 반환한다. */
	@Query("SELECT a.articleId FROM Article a "
			+ "WHERE a.articleId IN :articleIds AND a.analysisStatus = :analysisStatus")
	List<Long> findArticleIdsByIdInAndAnalysisStatus(
			@Param("articleIds") Collection<Long> articleIds,
			@Param("analysisStatus") AnalysisStatus analysisStatus);
}

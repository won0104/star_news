package com.starlightnews.backend.domain.article.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.SummaryStatus;
import org.springframework.data.domain.Limit;
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
			+ " content_type, content_hash, analysis_status) "
			+ "VALUES (:organizationId, :title, :url, :urlHash, :publishedAt, :sourceCategory, "
			+ " :content, :contentType, :contentHash, :analysisStatus) "
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
			@Param("contentHash") byte[] contentHash,
			@Param("analysisStatus") String analysisStatus);

	/**
	 * 같은 본문으로 이미 저장된 기사들의 제목.
	 *
	 * <p>본문이 같은데 제목이 다르면 그 본문은 기사 본문이 아니다. 사이트의 추천 기사 목록 같은
	 * 것이 본문 자리에 들어온 경우라, 저장하지 않는다.
	 */
	@Query("SELECT DISTINCT a.title FROM Article a WHERE a.contentHash = :contentHash")
	List<String> findTitlesByContentHash(@Param("contentHash") byte[] contentHash);

	/** url 해시로 기사 ID 를 찾는다. 저장 여부 확인용. */
	@Query("SELECT a.articleId FROM Article a WHERE a.urlHash = :urlHash")
	Optional<Long> findIdByUrlHash(@Param("urlHash") byte[] urlHash);

	/** 지정한 분석 상태의 기사 상세와 언론사를 한 번에 조회한다. */
	@Query("SELECT a FROM Article a JOIN FETCH a.organization "
			+ "WHERE a.articleId = :articleId AND a.analysisStatus = :analysisStatus")
	Optional<Article> findDetailByArticleId(
			@Param("articleId") Long articleId,
			@Param("analysisStatus") AnalysisStatus analysisStatus);

	/** 기사 요약 생성 판단과 GMS 입력에 필요한 필드만 조회한다. */
	interface ArticleSummaryTarget {
		Long getArticleId();

		String getTitle();

		String getContent();

		String getSummary();

		SummaryStatus getSummaryStatus();
	}

	/** 분석이 완료된 기사만 요약 생성 대상으로 조회한다. */
	Optional<ArticleSummaryTarget> findSummaryTargetByArticleIdAndAnalysisStatus(
			Long articleId, AnalysisStatus analysisStatus);

	/** NOT_REQUESTED 또는 FAILED 상태를 PROCESSING 으로 바꿔 요약 생성 권한을 선점한다. */
	@Modifying(clearAutomatically = true, flushAutomatically = true)
	@Query("UPDATE Article a SET a.summaryStatus = :processingStatus "
			+ "WHERE a.articleId = :articleId "
			+ "AND a.analysisStatus = :analysisStatus "
			+ "AND a.summaryStatus IN :claimableStatuses")
	int claimSummaryGeneration(
			@Param("articleId") Long articleId,
			@Param("analysisStatus") AnalysisStatus analysisStatus,
			@Param("processingStatus") SummaryStatus processingStatus,
			@Param("claimableStatuses") Collection<SummaryStatus> claimableStatuses);

	/** PROCESSING 상태인 기사에 생성된 요약을 저장한다. */
	@Modifying(clearAutomatically = true, flushAutomatically = true)
	@Query("UPDATE Article a SET a.summary = :summary, a.summaryStatus = :completedStatus, "
			+ "a.summaryGeneratedAt = :generatedAt "
			+ "WHERE a.articleId = :articleId AND a.summaryStatus = :processingStatus")
	int completeSummaryGeneration(
			@Param("articleId") Long articleId,
			@Param("summary") String summary,
			@Param("generatedAt") LocalDateTime generatedAt,
			@Param("processingStatus") SummaryStatus processingStatus,
			@Param("completedStatus") SummaryStatus completedStatus);

	/** PROCESSING 상태인 기사의 요약 생성 실패를 기록한다. */
	@Modifying(clearAutomatically = true, flushAutomatically = true)
	@Query("UPDATE Article a SET a.summaryStatus = :failedStatus "
			+ "WHERE a.articleId = :articleId AND a.summaryStatus = :processingStatus")
	int failSummaryGeneration(
			@Param("articleId") Long articleId,
			@Param("processingStatus") SummaryStatus processingStatus,
			@Param("failedStatus") SummaryStatus failedStatus);

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

	/**
	 * AI 분석 결과를 반영한다.
	 *
	 * <p>분석 대기(PROCESSING) 중인 기사만 바꾼다. 그사이 다른 경로가 상태를 바꿨으면 덮어쓰지 않는다.
	 *
	 * @return 바뀐 행 수. 0 이면 이미 분석 대기가 아니었다
	 */
	@Modifying
	@Query("UPDATE Article a SET a.nodeId = :nodeId, a.topicCode = :topicCode, "
			+ "a.subtopicCode = :subtopicCode, a.analysisFailureCode = NULL, "
			+ "a.analysisStatus = com.starlightnews.backend.global.enums.AnalysisStatus.COMPLETED "
			+ "WHERE a.articleId = :articleId "
			+ "AND a.analysisStatus = com.starlightnews.backend.global.enums.AnalysisStatus.PROCESSING")
	int markAnalyzed(@Param("articleId") Long articleId,
			@Param("nodeId") String nodeId,
			@Param("topicCode") String topicCode,
			@Param("subtopicCode") String subtopicCode);

	/**
	 * 분석할 수 없는 기사로 표시한다. 다시 불러도 같은 결과라 분석 대상에서 뺀다.
	 *
	 * @return 바뀐 행 수. 0 이면 이미 분석 대기가 아니었다
	 */
	@Modifying
	@Query("UPDATE Article a "
			+ "SET a.analysisStatus = com.starlightnews.backend.global.enums.AnalysisStatus.DROPPED, "
			+ "    a.analysisFailureCode = :failureCode "
			+ "WHERE a.articleId = :articleId "
			+ "AND a.analysisStatus = com.starlightnews.backend.global.enums.AnalysisStatus.PROCESSING")
	int markAnalysisRejected(@Param("articleId") Long articleId,
			@Param("failureCode") String failureCode);

	/**
	 * 일시 실패를 한 번 센다. 한도에 닿으면 FAILED 로 두어 더 부르지 않는다.
	 *
	 * <p><b>상태를 먼저 대입해야 한다.</b> MySQL 은 SET 을 왼쪽부터 평가하고 앞에서 바꾼 값을 뒤에서
	 * 그대로 본다. 횟수를 먼저 올리면 뒤의 비교가 이미 올라간 값에 다시 1 을 더해, 한도보다 한 번
	 * 일찍 FAILED 가 된다.
	 *
	 * @return 바뀐 행 수. 0 이면 이미 분석 대기가 아니었다
	 */
	@Modifying
	@Query("UPDATE Article a "
			+ "SET a.analysisStatus = CASE WHEN a.analysisAttempts + 1 >= :maxAttempts "
			+ "        THEN com.starlightnews.backend.global.enums.AnalysisStatus.FAILED "
			+ "        ELSE com.starlightnews.backend.global.enums.AnalysisStatus.PROCESSING END, "
			+ "    a.analysisAttempts = a.analysisAttempts + 1, "
			+ "    a.analysisFailureCode = :failureCode "
			+ "WHERE a.articleId = :articleId "
			+ "AND a.analysisStatus = com.starlightnews.backend.global.enums.AnalysisStatus.PROCESSING")
	int recordAnalysisFailure(@Param("articleId") Long articleId, @Param("maxAttempts") int maxAttempts,
			@Param("failureCode") String failureCode);

	/** 기사의 현재 분석 상태. */
	@Query("SELECT a.analysisStatus FROM Article a WHERE a.articleId = :articleId")
	Optional<AnalysisStatus> findAnalysisStatus(@Param("articleId") Long articleId);

	/** AI 분석에 넘길 기사 한 건. */
	interface AnalysisTarget {
		Long getArticleId();

		String getTitle();

		String getContent();

		Long getOrganizationId();

		String getOrganizationName();

		LocalDateTime getPublishedAt();
	}

	/**
	 * 분석 대기 중인 기사를 시도 횟수가 적은 순, 같으면 오래된 순으로 고른다.
	 *
	 */
	@Query("SELECT a.articleId AS articleId, a.title AS title, a.content AS content, "
			+ "o.id AS organizationId, o.name AS organizationName, a.publishedAt AS publishedAt "
			+ "FROM Article a JOIN a.organization o "
			+ "WHERE a.analysisStatus = com.starlightnews.backend.global.enums.AnalysisStatus.PROCESSING "
			+ "AND a.nodeId IS NULL "
			+ "AND a.analysisAttempts < :maxAttempts "
			+ "ORDER BY a.analysisAttempts ASC, a.articleId ASC")
	List<AnalysisTarget> findAnalysisQueue(@Param("maxAttempts") int maxAttempts, Limit limit);

	/** 분석 대기 중인 기사 전체 수. 회차당 상한과 무관하게 얼마나 밀렸는지 본다. */
	@Query("SELECT COUNT(a) FROM Article a "
			+ "WHERE a.analysisStatus = com.starlightnews.backend.global.enums.AnalysisStatus.PROCESSING "
			+ "AND a.nodeId IS NULL "
			+ "AND a.analysisAttempts < :maxAttempts")
	long countAnalysisQueue(@Param("maxAttempts") int maxAttempts);

	/**
	 * 분석 대기 중인 기사 중 가장 오래 기다린 것이 수집된 지 몇 분 됐는지. 대기가 없으면 null.
	 *
	 * <p>DB 안에서 뺀다. created_at 은 컬럼 기본값(DB 서버 시각)으로 찍혀, 애플리케이션 시각과
	 * 견주면 서버 시간대가 다를 때 몇 시간씩 어긋난다.
	 */
	@Query(value = "SELECT TIMESTAMPDIFF(MINUTE, MIN(created_at), NOW()) FROM articles "
			+ "WHERE analysis_status = 'PROCESSING' AND node_id IS NULL "
			+ "AND analysis_attempts < :maxAttempts", nativeQuery = true)
	Long findOldestAnalysisWaitMinutes(@Param("maxAttempts") int maxAttempts);

	/** 주어진 ID 중 지정한 분석 상태의 기사 ID만 반환한다. */
	@Query("SELECT a.articleId FROM Article a "
			+ "WHERE a.articleId IN :articleIds AND a.analysisStatus = :analysisStatus")
	List<Long> findArticleIdsByIdInAndAnalysisStatus(
			@Param("articleIds") Collection<Long> articleIds,
			@Param("analysisStatus") AnalysisStatus analysisStatus);

	/** 시연 화면이 쓰는 기사 한 행. 분석 요청에 필요한 값과 그래프 진입점을 함께 담는다. */
	interface DemoArticle {
		Long getArticleId();

		/** Neo4j Article Node 의 nodeId. 분석 전이면 null. */
		String getNodeId();

		String getTopicCode();

		String getSubtopicCode();

		LocalDateTime getPublishedAt();

		Long getOrganizationId();

		String getOrganizationName();
	}

	/** 시연 기사 한 건을 언론사와 함께 조회한다. 분석 상태는 가리지 않는다. */
	@Query("SELECT a.articleId AS articleId, a.nodeId AS nodeId, a.topicCode AS topicCode, "
			+ "a.subtopicCode AS subtopicCode, a.publishedAt AS publishedAt, "
			+ "o.id AS organizationId, o.name AS organizationName "
			+ "FROM Article a JOIN a.organization o WHERE a.articleId = :articleId")
	Optional<DemoArticle> findDemoArticle(@Param("articleId") Long articleId);
}

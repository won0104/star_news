package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;

import com.starlightnews.backend.domain.user.domain.ArticleRead;
import com.starlightnews.backend.domain.user.domain.ArticleReadId;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 사용자 기사 열람 기록 조회·저장. (article_reads)
 */
public interface ArticleReadRepository extends Repository<ArticleRead, ArticleReadId> {

	ArticleRead save(ArticleRead articleRead);

	/**
	 * 열람 기록을 한 문장으로 저장하거나 갱신한다.
	 * 처음이면 click_count=1 로 INSERT 하고, 이미 있으면 first_read_at 은 그대로 둔 채
	 * last_read_at 을 갱신하고 click_count 를 1 늘린다.
	 *
	 * <p>UPDATE 를 먼저 치고 0 행이면 INSERT 하는 방식은 쓰지 않는다. 없는 행에 UPDATE 를 치면
	 * InnoDB 가 갭 락을 잡고, 같은 (user_id, article_id) 로 동시에 들어온 요청들이 그 갭에
	 * INSERT 하려다 서로 대기해 데드락이 난다(실측: 동시 10건 중 9건 실패).
	 *
	 * @return MySQL 영향 행 수. INSERT 되면 1, 기존 행이 갱신되면 2. (last_read_at 이 항상 바뀌므로 0 은 나오지 않는다)
	 */
	@Modifying
	@Query(value = "INSERT INTO article_reads "
			+ "(user_id, article_id, first_read_at, last_read_at, click_count) "
			+ "VALUES (:userId, :articleId, :now, :now, 1) "
			+ "ON DUPLICATE KEY UPDATE last_read_at = :now, click_count = click_count + 1",
			nativeQuery = true)
	int upsertRead(@Param("userId") Long userId, @Param("articleId") Long articleId,
			@Param("now") LocalDateTime now);

	/** Topic 코드별 집계 결과 한 행. */
	interface TopicReadCount {
		String getTopicCode();

		long getCount();
	}

	/** 개인 그래프 Node 별 읽은 기사 목록 한 행. */
	interface ReadArticleRow {
		Long getArticleId();

		String getTitle();

		String getOrganizationName();

		String getTopicCode();

		LocalDateTime getLastReadAt();

		String getSummary();
	}

	/** 사용자 전체 열람 기록 한 행. (ReadArticleRow 에 clickCount 가 추가됨) */
	interface HistoryRow {
		Long getArticleId();

		String getTitle();

		String getOrganizationName();

		String getTopicCode();

		LocalDateTime getLastReadAt();

		int getClickCount();

		String getSummary();
	}

	/**
	 * 해당 사용자가 읽은 기사를 articles.topic_code 기준으로 묶어 Topic 별 개수를 센다.
	 * topic_code 가 없는 기사는 집계에서 제외한다.
	 */
	@Query("SELECT a.topicCode AS topicCode, COUNT(r) AS count "
			+ "FROM ArticleRead r, Article a "
			+ "WHERE a.articleId = r.id.articleId "
			+ "AND r.id.userId = :userId "
			+ "AND a.topicCode IS NOT NULL "
			+ "GROUP BY a.topicCode")
	List<TopicReadCount> countReadArticlesByTopic(@Param("userId") Long userId);

	/**
	 * candidateArticleIds(Neo4j 에서 조회한 Node 관련 기사) 중 이 사용자가 실제로 읽은 것만,
	 * lastReadAt DESC, articleId DESC 로 첫 페이지를 가져온다.
	 */
	@Query("SELECT a.articleId AS articleId, a.title AS title, a.organization.name AS organizationName, "
			+ "a.topicCode AS topicCode, r.lastReadAt AS lastReadAt, a.summary AS summary "
			+ "FROM ArticleRead r, Article a "
			+ "WHERE a.articleId = r.id.articleId "
			+ "AND r.id.userId = :userId "
			+ "AND r.id.articleId IN :candidateArticleIds "
			+ "ORDER BY r.lastReadAt DESC, r.id.articleId DESC")
	List<ReadArticleRow> findFirstReadPage(@Param("userId") Long userId,
			@Param("candidateArticleIds") Collection<Long> candidateArticleIds, Pageable pageable);

	/** 위와 같지만 cursor 위치(lastReadAt, articleId) 다음부터 가져온다. */
	@Query("SELECT a.articleId AS articleId, a.title AS title, a.organization.name AS organizationName, "
			+ "a.topicCode AS topicCode, r.lastReadAt AS lastReadAt, a.summary AS summary "
			+ "FROM ArticleRead r, Article a "
			+ "WHERE a.articleId = r.id.articleId "
			+ "AND r.id.userId = :userId "
			+ "AND r.id.articleId IN :candidateArticleIds "
			+ "AND (r.lastReadAt < :cursorLastReadAt "
			+ "     OR (r.lastReadAt = :cursorLastReadAt AND r.id.articleId < :cursorArticleId)) "
			+ "ORDER BY r.lastReadAt DESC, r.id.articleId DESC")
	List<ReadArticleRow> findNextReadPage(@Param("userId") Long userId,
			@Param("candidateArticleIds") Collection<Long> candidateArticleIds,
			@Param("cursorLastReadAt") LocalDateTime cursorLastReadAt,
			@Param("cursorArticleId") Long cursorArticleId,
			Pageable pageable);

	/**
	 * 사용자의 전체 열람 기록을 lastReadAt DESC, articleId DESC 로 첫 페이지 가져온다.
	 * topicCode 가 null 이면 전체, 있으면 그 Topic 만 필터한다.
	 */
	@Query("SELECT a.articleId AS articleId, a.title AS title, a.organization.name AS organizationName, "
			+ "a.topicCode AS topicCode, r.lastReadAt AS lastReadAt, r.clickCount AS clickCount, a.summary AS summary "
			+ "FROM ArticleRead r, Article a "
			+ "WHERE a.articleId = r.id.articleId "
			+ "AND r.id.userId = :userId "
			+ "AND (:topicCode IS NULL OR a.topicCode = :topicCode) "
			+ "ORDER BY r.lastReadAt DESC, r.id.articleId DESC")
	List<HistoryRow> findFirstHistoryPage(@Param("userId") Long userId,
			@Param("topicCode") String topicCode, Pageable pageable);

	/** 위와 같지만 cursor 위치(lastReadAt, articleId) 다음부터 가져온다. */
	@Query("SELECT a.articleId AS articleId, a.title AS title, a.organization.name AS organizationName, "
			+ "a.topicCode AS topicCode, r.lastReadAt AS lastReadAt, r.clickCount AS clickCount, a.summary AS summary "
			+ "FROM ArticleRead r, Article a "
			+ "WHERE a.articleId = r.id.articleId "
			+ "AND r.id.userId = :userId "
			+ "AND (:topicCode IS NULL OR a.topicCode = :topicCode) "
			+ "AND (r.lastReadAt < :cursorLastReadAt "
			+ "     OR (r.lastReadAt = :cursorLastReadAt AND r.id.articleId < :cursorArticleId)) "
			+ "ORDER BY r.lastReadAt DESC, r.id.articleId DESC")
	List<HistoryRow> findNextHistoryPage(@Param("userId") Long userId,
			@Param("topicCode") String topicCode,
			@Param("cursorLastReadAt") LocalDateTime cursorLastReadAt,
			@Param("cursorArticleId") Long cursorArticleId,
			Pageable pageable);
}

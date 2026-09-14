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
	 * 해당 Row 가 있으면 click_count 를 1 늘리고 last_read_at 을 갱신한다. first_read_at 은 건드리지 않는다.
	 * 반환값은 갱신된 행 수(있으면 1, 없으면 0)이며, 0 이면 호출 측이 새 Row 를 만든다.
	 */
	@Modifying
	@Query("UPDATE ArticleRead r "
			+ "SET r.clickCount = r.clickCount + 1, r.lastReadAt = :now "
			+ "WHERE r.id = :id")
	int incrementRead(@Param("id") ArticleReadId id, @Param("now") LocalDateTime now);

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

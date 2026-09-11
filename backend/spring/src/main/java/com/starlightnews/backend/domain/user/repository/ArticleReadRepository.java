package com.starlightnews.backend.domain.user.repository;

import java.util.List;

import com.starlightnews.backend.domain.user.domain.ArticleRead;
import com.starlightnews.backend.domain.user.domain.ArticleReadId;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 사용자 기사 열람 기록 조회 (읽기 전용).
 */
public interface ArticleReadRepository extends Repository<ArticleRead, ArticleReadId> {

	/** Topic 코드별 집계 결과 한 행. */
	interface TopicReadCount {
		String getTopicCode();

		long getCount();
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
}

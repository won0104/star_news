package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;

import com.starlightnews.backend.domain.user.domain.UserArticleFavorite;
import com.starlightnews.backend.domain.user.domain.UserArticleFavoriteId;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * 사용자 기사 즐겨찾기 조회 및 변경.
 */
public interface UserArticleFavoriteRepository
		extends JpaRepository<UserArticleFavorite, UserArticleFavoriteId> {

	/** 기사 북마크 목록 응답에 필요한 MySQL 조회 결과 한 행. */
	interface ArticleBookmarkRow {
		Long getArticleId();

		String getTitle();

		String getPublisher();

		LocalDateTime getPublishedAt();

		String getSummary();

		LocalDateTime getBookmarkedAt();
	}

	/** 주어진 articleId 중 해당 사용자가 즐겨찾기한 것만 반환한다. */
	@Query("SELECT f.id.articleId FROM UserArticleFavorite f "
			+ "WHERE f.id.userId = :userId AND f.id.articleId IN :articleIds")
	List<Long> findFavoritedArticleIds(@Param("userId") Long userId,
			@Param("articleIds") Collection<Long> articleIds);

	/** 사용자의 공개 기사 북마크를 최신 등록순으로 첫 페이지 조회한다. */
	@Query("SELECT a.articleId AS articleId, a.title AS title, a.organization.name AS publisher, "
			+ "a.publishedAt AS publishedAt, a.summary AS summary, f.favoritedAt AS bookmarkedAt "
			+ "FROM UserArticleFavorite f, Article a "
			+ "WHERE a.articleId = f.id.articleId "
			+ "AND f.id.userId = :userId "
			+ "AND a.analysisStatus = :analysisStatus "
			+ "ORDER BY f.favoritedAt DESC, f.id.articleId DESC")
	List<ArticleBookmarkRow> findFirstArticleBookmarkPage(
			@Param("userId") Long userId,
			@Param("analysisStatus") AnalysisStatus analysisStatus,
			Pageable pageable);

	/** 위와 같지만 cursor 위치(bookmarkedAt, articleId) 다음부터 조회한다. */
	@Query("SELECT a.articleId AS articleId, a.title AS title, a.organization.name AS publisher, "
			+ "a.publishedAt AS publishedAt, a.summary AS summary, f.favoritedAt AS bookmarkedAt "
			+ "FROM UserArticleFavorite f, Article a "
			+ "WHERE a.articleId = f.id.articleId "
			+ "AND f.id.userId = :userId "
			+ "AND a.analysisStatus = :analysisStatus "
			+ "AND (f.favoritedAt < :cursorBookmarkedAt "
			+ "     OR (f.favoritedAt = :cursorBookmarkedAt AND f.id.articleId < :cursorArticleId)) "
			+ "ORDER BY f.favoritedAt DESC, f.id.articleId DESC")
	List<ArticleBookmarkRow> findNextArticleBookmarkPage(
			@Param("userId") Long userId,
			@Param("analysisStatus") AnalysisStatus analysisStatus,
			@Param("cursorBookmarkedAt") LocalDateTime cursorBookmarkedAt,
			@Param("cursorArticleId") Long cursorArticleId,
			Pageable pageable);

	/** 지정 사용자의 선택된 기사 북마크를 한 번에 삭제한다. */
	@Modifying(clearAutomatically = true, flushAutomatically = true)
	@Query("DELETE FROM UserArticleFavorite f "
			+ "WHERE f.id.userId = :userId AND f.id.articleId IN :articleIds")
	int deleteByUserIdAndArticleIds(
			@Param("userId") Long userId,
			@Param("articleIds") Collection<Long> articleIds);
}

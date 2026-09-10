package com.starlightnews.backend.domain.user.repository;

import java.util.Collection;
import java.util.List;

import com.starlightnews.backend.domain.user.domain.UserArticleFavorite;
import com.starlightnews.backend.domain.user.domain.UserArticleFavoriteId;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 사용자 기사 즐겨찾기 조회 (읽기 전용).
 */
public interface UserArticleFavoriteRepository
		extends Repository<UserArticleFavorite, UserArticleFavoriteId> {

	/** 주어진 articleId 중 해당 사용자가 즐겨찾기한 것만 반환한다. */
	@Query("SELECT f.id.articleId FROM UserArticleFavorite f "
			+ "WHERE f.id.userId = :userId AND f.id.articleId IN :articleIds")
	List<Long> findFavoritedArticleIds(@Param("userId") Long userId,
			@Param("articleIds") Collection<Long> articleIds);
}

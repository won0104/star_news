package com.starlightnews.backend.domain.user.repository;

import com.starlightnews.backend.domain.user.domain.UserNodeFavorite;
import com.starlightnews.backend.domain.user.domain.UserNodeFavoriteId;
import org.springframework.data.repository.Repository;

/**
 * 사용자 Node 즐겨찾기 조회 (읽기 전용).
 */
public interface UserNodeFavoriteRepository extends Repository<UserNodeFavorite, UserNodeFavoriteId> {

	boolean existsById(UserNodeFavoriteId id);
}

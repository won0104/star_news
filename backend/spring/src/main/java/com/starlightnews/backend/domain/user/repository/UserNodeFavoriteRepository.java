package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;

import com.starlightnews.backend.domain.user.domain.UserNodeFavorite;
import com.starlightnews.backend.domain.user.domain.UserNodeFavoriteId;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 사용자 Node 즐겨찾기 조회 (읽기 전용).
 */
public interface UserNodeFavoriteRepository extends Repository<UserNodeFavorite, UserNodeFavoriteId> {

	/** 즐겨찾기 Node 목록 조회 결과 한 행. */
	interface NodeFavoriteRow {
		String getNodeType();

		String getNodeId();

		LocalDateTime getBookmarkedAt();
	}

	boolean existsById(UserNodeFavoriteId id);

	/** 허용된 유형의 Node 즐겨찾기를 최신 등록순으로 첫 페이지 조회한다. */
	@Query(value = """
			SELECT node_type AS nodeType, node_id AS nodeId, favorited_at AS bookmarkedAt
			FROM user_node_favorites
			WHERE user_id = :userId AND node_type IN (:nodeTypes)
			ORDER BY favorited_at DESC, node_type ASC, node_id ASC
			""", nativeQuery = true)
	List<NodeFavoriteRow> findFirstNodeFavoritePage(
			@Param("userId") Long userId,
			@Param("nodeTypes") Collection<String> nodeTypes,
			Pageable pageable);

	/** 위와 같지만 cursor 위치(bookmarkedAt, nodeType, nodeId) 다음부터 조회한다. */
	@Query(value = """
			SELECT node_type AS nodeType, node_id AS nodeId, favorited_at AS bookmarkedAt
			FROM user_node_favorites
			WHERE user_id = :userId
			  AND node_type IN (:nodeTypes)
			  AND (
			       favorited_at < :cursorBookmarkedAt
			       OR (favorited_at = :cursorBookmarkedAt AND node_type > :cursorNodeType)
			       OR (favorited_at = :cursorBookmarkedAt
			           AND node_type = :cursorNodeType AND node_id > :cursorNodeId)
			  )
			ORDER BY favorited_at DESC, node_type ASC, node_id ASC
			""", nativeQuery = true)
	List<NodeFavoriteRow> findNextNodeFavoritePage(
			@Param("userId") Long userId,
			@Param("nodeTypes") Collection<String> nodeTypes,
			@Param("cursorBookmarkedAt") LocalDateTime cursorBookmarkedAt,
			@Param("cursorNodeType") String cursorNodeType,
			@Param("cursorNodeId") String cursorNodeId,
			Pageable pageable);
}

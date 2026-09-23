package com.starlightnews.backend.domain.usergraph.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;

import com.starlightnews.backend.domain.user.domain.User;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * User Graph 동기화에 보낼 사용자 상태를 MySQL 에서 집계한다.
 *
 * <p>사용자 한 명씩 조회하지 않고 ID 목록으로 한 번에 읽는다. 회차마다 전체 사용자를 보내므로
 * 사용자 수만큼 쿼리가 나가면 그대로 N+1 이 된다.
 *
 * <p>집계 기준을 이 한 곳에 모아 둔다. "무엇을 관심으로 볼 것인가"는 추천 로직이 자리잡으면
 * 바뀔 수 있는 판단이라, 바뀔 때 고칠 곳이 흩어지지 않게 한다.
 */
public interface UserGraphAggregationRepository extends Repository<User, Long> {

	/** 즐겨찾기에서 뽑은 관심 Node 한 행. */
	interface InterestNodeRow {
		Long getUserId();

		String getNodeType();

		String getNodeId();
	}

	/** 사용자가 직접 설정한 관심·비관심 Topic 한 행. */
	interface TopicPreferenceRow {
		Long getUserId();

		String getTopicCode();
	}

	/** Event 소비 집계 한 행. */
	interface ConsumedEventRow {
		Long getUserId();

		String getNodeId();

		Integer getClickCount();

		LocalDateTime getLastSeenAt();

		/**
		 * 이 Event 를 즐겨찾기했으면 1, 아니면 0. FastAPI 가 CONSUMED 관계의 속성으로 반영한다.
		 *
		 * <p>MySQL 에 boolean 타입이 없어 정수로 온다.
		 */
		Integer getFavorited();
	}

	/**
	 * 동기화 대상 사용자 ID 를 오름차순으로 한 페이지 조회한다.
	 *
	 * <p>탈퇴 회원은 제외한다. 추천을 받을 일이 없고, Neo4j 에 관계를 남겨 둘 이유도 없다.
	 */
	@Query(value = """
			SELECT user_id
			FROM users
			WHERE deleted_at IS NULL
			ORDER BY user_id
			""", nativeQuery = true)
	List<Long> findSyncTargetUserIds(Pageable pageable);

	/**
	 * 즐겨찾기한 Node 중 관심 관계로 보낼 것들을 조회한다.
	 *
	 * <p>{@code nodeTypes} 로 유형을 좁힌다. 명세상 INTERESTED_IN 의 대상은 Entity·Topic·Story 인데
	 * Topic 은 즐겨찾기 대상이 아니고, Event 즐겨찾기는 소비 관계로 따로 전달된다.
	 */
	@Query(value = """
			SELECT user_id AS userId, node_type AS nodeType, node_id AS nodeId
			FROM user_node_favorites
			WHERE user_id IN (:userIds) AND node_type IN (:nodeTypes)
			ORDER BY user_id, node_type, node_id
			""", nativeQuery = true)
	List<InterestNodeRow> findFavoriteInterestNodes(
			@Param("userIds") Collection<Long> userIds,
			@Param("nodeTypes") Collection<String> nodeTypes);

	/**
	 * 가입·설정에서 고른 관심 또는 비관심 Topic 을 조회한다.
	 *
	 * @param interestType {@code INTEREST} 또는 {@code DISLIKE}
	 */
	@Query(value = """
			SELECT user_id AS userId, topic_code AS topicCode
			FROM user_interest
			WHERE user_id IN (:userIds) AND interest_type = :interestType
			ORDER BY user_id, topic_code
			""", nativeQuery = true)
	List<TopicPreferenceRow> findTopicPreferences(
			@Param("userIds") Collection<Long> userIds,
			@Param("interestType") String interestType);

	/**
	 * Event 소비 집계를 조회한다.
	 *
	 * <p>클릭·대표 열람·즐겨찾기 중 하나라도 있으면 보낸다. FastAPI 는 이 관계를 두 가지로 쓰는데,
	 * 하나는 "이미 본 Event 를 추천에서 빼는" 미열람 필터이고 다른 하나는 취향 벡터 가중치다.
	 * 앞쪽 기준으로는 기사를 읽은 것만으로도 본 것이므로, 클릭만 보면 읽은 내용을 다시 추천한다.
	 * 기사를 목록에서 눌러 읽는 쪽이 그래프에서 노드를 클릭하는 것보다 훨씬 흔하다.
	 *
	 * <p><b>열람은 대표 사건만 본다.</b> 기사 한 건이 COVERS 로 사건 열 개 넘게 이어지는데 대부분은
	 * 스치듯 언급된 부차 사건이다. 전부 보내면 기사 한 건을 읽을 때마다 사건 열댓 개가 추천 후보에서
	 * 빠지는데, 클릭이 0 이라 취향 벡터에는 기여하지 않는다. 후보만 마른다.
	 * 부차 사건도 화면(개인 그래프)에는 그대로 남는다. read_article_count 는 건드리지 않는다.
	 *
	 * <p>{@code eventClickCount} 로 보내는 값은 그대로 클릭 수다. 클릭이 0 이면 가중치가
	 * {@code log(1+0)=0} 이라 취향 벡터에는 영향이 없고 미열람 필터에만 걸린다.
	 */
	@Query(value = """
			SELECT node.user_id AS userId, node.node_id AS nodeId,
			       node.node_click_count AS clickCount, node.last_seen_at AS lastSeenAt,
			       CASE WHEN favorite.user_id IS NOT NULL THEN 1 ELSE 0 END AS favorited
			FROM user_knowledge_nodes node
			LEFT JOIN user_node_favorites favorite
			       ON favorite.user_id = node.user_id
			      AND favorite.node_type = 'EVENT'
			      AND favorite.node_id = node.node_id
			WHERE node.user_id IN (:userIds)
			  AND node.node_type = 'EVENT'
			  AND (node.node_click_count > 0
			       OR node.primary_read_count > 0
			       OR favorite.user_id IS NOT NULL)
			ORDER BY node.user_id, node.node_id
			""", nativeQuery = true)
	List<ConsumedEventRow> findConsumedEvents(@Param("userIds") Collection<Long> userIds);
}

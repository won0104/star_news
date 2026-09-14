package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.global.enums.NodeType;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 사용자 지식 Node 참조 정보 조회·저장. (user_knowledge_nodes)
 */
public interface UserKnowledgeNodeRepository
		extends Repository<UserKnowledgeNode, UserKnowledgeNodeId> {

	Optional<UserKnowledgeNode> findById(UserKnowledgeNodeId id);

	UserKnowledgeNode save(UserKnowledgeNode userKnowledgeNode);

	/**
	 * 해당 Row 가 있으면 node_click_count 를 1 늘리고 last_seen_at 을 갱신한다.
	 * 반환값은 갱신된 행 수(있으면 1, 없으면 0)이며, 0 이면 호출 측이 새 Row 를 만든다.
	 */
	@Modifying
	@Query("UPDATE UserKnowledgeNode u "
			+ "SET u.nodeClickCount = u.nodeClickCount + 1, u.lastSeenAt = :now "
			+ "WHERE u.id = :id")
	int incrementClick(@Param("id") UserKnowledgeNodeId id, @Param("now") LocalDateTime now);

	/**
	 * 기사 열람으로 얻은 개인 Node 를 한 문장으로 저장하거나 갱신한다.
	 * 처음 보는 Node 면 read_article_count=1 로 INSERT 하고(이 기사가 그 Node 를 건드린 첫 고유 기사),
	 * 이미 있으면 node_label·topic_code·first_seen_at 은 그대로 둔 채 last_seen_at 을 갱신하고
	 * read_article_count 에 readIncrement 를 더한다.
	 *
	 * <p>readIncrement 는 이 기사를 처음 읽을 때만 1, 재열람이면 0 이다.
	 * read_article_count 가 그 Node 를 건드린 고유 기사 수라 같은 기사 재열람으로는 늘면 안 된다.
	 *
	 * <p>UPDATE 를 먼저 치고 0 행이면 INSERT 하는 방식은 동시 요청에서 InnoDB 갭 락 데드락을 일으켜 쓰지 않는다.
	 */
	@Modifying
	@Query(value = "INSERT INTO user_knowledge_nodes "
			+ "(user_id, node_type, node_id, node_label, topic_code, "
			+ " read_article_count, node_click_count, first_seen_at, last_seen_at) "
			+ "VALUES (:userId, :nodeType, :nodeId, :nodeLabel, :topicCode, 1, 0, :now, :now) "
			+ "ON DUPLICATE KEY UPDATE "
			+ " read_article_count = read_article_count + :readIncrement, last_seen_at = :now",
			nativeQuery = true)
	int upsertRead(@Param("userId") Long userId, @Param("nodeType") String nodeType,
			@Param("nodeId") String nodeId, @Param("nodeLabel") String nodeLabel,
			@Param("topicCode") String topicCode, @Param("readIncrement") int readIncrement,
			@Param("now") LocalDateTime now);

	/** 해당 사용자의 특정 Topic 개인 Node 전체. (개인 그래프 Topic 스냅샷용) */
	@Query("SELECT u FROM UserKnowledgeNode u "
			+ "WHERE u.id.userId = :userId AND u.topicCode = :topicCode")
	List<UserKnowledgeNode> findByUserIdAndTopicCode(@Param("userId") Long userId,
			@Param("topicCode") String topicCode);

	/** Topic 별 클릭한(참여) Node 개수 한 행. */
	interface TopicNodeCount {
		String getTopicCode();

		long getCount();
	}

	/**
	 * 사용자의 특정 Topic·nodeType 범위에서 중요도(읽은 기사 수+클릭 수) 상위 Node 만 가져온다.
	 * (개인 그래프 요약의 Topic 별 대표 Node 조회용. 전체를 끌어와 자바에서 자르지 않고 DB에서 상위 N개만 받는다.)
	 * 동률이면 읽은 기사 수 DESC, nodeId ASC 순으로 결과를 고정한다.
	 */
	@Query(value = "SELECT * FROM user_knowledge_nodes FORCE INDEX (idx_user_knowledge_nodes_user_topic_type) "
			+ "WHERE user_id = :userId AND topic_code = :topicCode AND node_type IN (:nodeTypeNames) "
			+ "ORDER BY (read_article_count + node_click_count) DESC, read_article_count DESC, node_id ASC "
			+ "LIMIT :limit", nativeQuery = true)
	List<UserKnowledgeNode> findTopRepresentatives(@Param("userId") Long userId,
			@Param("topicCode") String topicCode, @Param("nodeTypeNames") Collection<String> nodeTypeNames,
			@Param("limit") int limit);

	/**
	 * 사용자가 클릭해본(node_click_count > 0) Node 개수를 Topic 별로 센다. (개인 그래프 요약의 참여도 계산용)
	 * topicCode 가 없는 Node 는 집계에서 제외한다.
	 */
	@Query("SELECT u.topicCode AS topicCode, COUNT(u) AS count FROM UserKnowledgeNode u "
			+ "WHERE u.id.userId = :userId AND u.id.nodeType IN :nodeTypes "
			+ "AND u.topicCode IS NOT NULL AND u.nodeClickCount > 0 "
			+ "GROUP BY u.topicCode")
	List<TopicNodeCount> countExploredNodesByTopic(@Param("userId") Long userId,
			@Param("nodeTypes") Collection<NodeType> nodeTypes);
}

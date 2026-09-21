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
	 * 해당 개인 Node 가 이미 있는지 확인한다. 잠금을 잡지 않는 일반 조회다.
	 * 없는 행에 UPDATE 를 먼저 쳐서 존재 여부를 알아내면 InnoDB 갭 락이 걸려 동시 첫 클릭이 데드락 난다.
	 */
	boolean existsById(UserKnowledgeNodeId id);

	/**
	 * 이미 있는 Row 의 node_click_count 를 1 늘리고 last_seen_at 을 갱신한다.
	 * 존재를 확인한 뒤에만 호출한다. (없는 행에 치면 갭 락이 걸린다)
	 */
	@Modifying
	@Query("UPDATE UserKnowledgeNode u "
			+ "SET u.nodeClickCount = u.nodeClickCount + 1, u.lastSeenAt = :now "
			+ "WHERE u.id = :id")
	int incrementClick(@Param("id") UserKnowledgeNodeId id, @Param("now") LocalDateTime now);

	/**
	 * 없던 개인 Node 를 첫 클릭으로 만든다. node_click_count=1, read_article_count=0.
	 * 동시에 같은 Node 로 첫 클릭이 들어와 이미 만들어졌으면 클릭 수만 1 늘린다.
	 *
	 * <p>INSERT 를 시도하고 제약 위반을 예외로 잡아 되돌리는 방식은 쓰지 않는다.
	 * 위반이 commit 시점에 나서 서비스의 try/catch 로는 잡히지 않기 때문이다.
	 */
	@Modifying
	@Query(value = "INSERT INTO user_knowledge_nodes "
			+ "(user_id, node_type, node_id, node_label, topic_code, "
			+ " read_article_count, node_click_count, first_seen_at, last_seen_at) "
			+ "VALUES (:userId, :nodeType, :nodeId, :nodeLabel, :topicCode, 0, 1, :now, :now) "
			+ "ON DUPLICATE KEY UPDATE "
			+ " node_click_count = node_click_count + 1, last_seen_at = :now",
			nativeQuery = true)
	int upsertClick(@Param("userId") Long userId, @Param("nodeType") String nodeType,
			@Param("nodeId") String nodeId, @Param("nodeLabel") String nodeLabel,
			@Param("topicCode") String topicCode, @Param("now") LocalDateTime now);

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

	/** 최근 주제 지형 Entity와 개인·전체 사용자의 전 기간 누적 기사 수. */
	interface NewsReportEntityLandscapeRow {
		String getNodeType();

		String getNodeKey();

		String getNodeLabel();

		String getTopicCode();

		long getUserReadArticleCount();

		long getGlobalReadArticleCount();

		LocalDateTime getFirstSeenAt();

		LocalDateTime getLastSeenAt();
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

	/**
	 * 최근 기간에 다시 접한 Entity 중 개인 누적 읽기 상위 Node와 전체 사용자 누적 읽기 합계를 조회한다.
	 * 기간은 후보를 고르는 데만 사용하며 두 읽기 수는 전 기간 누적값이다.
	 */
	@Query(value = "SELECT candidate.node_type AS nodeType, candidate.node_id AS nodeKey, "
			+ "candidate.node_label AS nodeLabel, candidate.topic_code AS topicCode, "
			+ "candidate.read_article_count AS userReadArticleCount, "
			+ "COALESCE(SUM(all_users.read_article_count), 0) AS globalReadArticleCount, "
			+ "candidate.first_seen_at AS firstSeenAt, candidate.last_seen_at AS lastSeenAt "
			+ "FROM user_knowledge_nodes AS candidate "
			+ "JOIN user_knowledge_nodes AS all_users FORCE INDEX (idx_user_knowledge_nodes_node_user) "
			+ "ON all_users.node_type = candidate.node_type AND all_users.node_id = candidate.node_id "
			+ "WHERE candidate.user_id = :userId AND candidate.node_type = 'ENTITY' "
			+ "AND candidate.read_article_count > 0 "
			+ "AND candidate.last_seen_at >= :fromInclusive AND candidate.last_seen_at < :toExclusive "
			+ "GROUP BY candidate.user_id, candidate.node_type, candidate.node_id, candidate.node_label, "
			+ "candidate.topic_code, candidate.read_article_count, candidate.first_seen_at, candidate.last_seen_at "
			+ "ORDER BY candidate.read_article_count DESC, globalReadArticleCount DESC, candidate.node_id ASC "
			+ "LIMIT :limit", nativeQuery = true)
	List<NewsReportEntityLandscapeRow> findEntityLandscapeForNewsReport(
			@Param("userId") Long userId,
			@Param("fromInclusive") LocalDateTime fromInclusive,
			@Param("toExclusive") LocalDateTime toExclusive,
			@Param("limit") int limit);
}

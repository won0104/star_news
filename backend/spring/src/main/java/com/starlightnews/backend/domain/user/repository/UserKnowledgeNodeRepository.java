package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
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

	/** 해당 사용자의 특정 Topic 개인 Node 전체. (개인 그래프 Topic 스냅샷용) */
	@Query("SELECT u FROM UserKnowledgeNode u "
			+ "WHERE u.id.userId = :userId AND u.topicCode = :topicCode")
	List<UserKnowledgeNode> findByUserIdAndTopicCode(@Param("userId") Long userId,
			@Param("topicCode") String topicCode);

	/** 해당 사용자의 개인 Node 전체. (개인 그래프 요약 조회용) */
	@Query("SELECT u FROM UserKnowledgeNode u WHERE u.id.userId = :userId")
	List<UserKnowledgeNode> findByUserId(@Param("userId") Long userId);
}

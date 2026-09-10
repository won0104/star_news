package com.starlightnews.backend.domain.user.repository;

import java.util.Optional;

import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import org.springframework.data.repository.Repository;

/**
 * 사용자 지식 Node 참조 정보 조회·저장. (user_knowledge_nodes)
 */
public interface UserKnowledgeNodeRepository
		extends Repository<UserKnowledgeNode, UserKnowledgeNodeId> {

	Optional<UserKnowledgeNode> findById(UserKnowledgeNodeId id);

	UserKnowledgeNode save(UserKnowledgeNode userKnowledgeNode);
}

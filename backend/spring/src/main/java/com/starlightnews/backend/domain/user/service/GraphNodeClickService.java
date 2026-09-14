package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.util.Optional;

import com.starlightnews.backend.domain.user.cache.ExploredNodeCountCache;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.domain.user.repository.NodeSnapshot;
import com.starlightnews.backend.domain.user.repository.NodeSnapshotRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 사용자가 그래프 Node 를 직접 클릭한 신호를 user_knowledge_nodes 에 기록한다.
 * 갱신을 먼저 시도하고(hot path 는 UPDATE 한 번), 대상 Row 가 없을 때만 Neo4j 스냅샷으로 새 Row 를 만든다.
 */
@Service
@RequiredArgsConstructor
public class GraphNodeClickService {

	private final UserKnowledgeNodeRepository userKnowledgeNodeRepository;
	private final NodeSnapshotRepository nodeSnapshotRepository;
	private final ExploredNodeCountCache exploredNodeCountCache;

	@Transactional
	public void recordClick(Long userId, NodeType nodeType, String nodeKey) {
		UserKnowledgeNodeId id = new UserKnowledgeNodeId(userId, nodeType, nodeKey);
		LocalDateTime now = LocalDateTime.now();

		if (userKnowledgeNodeRepository.incrementClick(id, now) == 1) {
			exploredNodeCountCache.evict(userId);
			return;
		}

		NodeSnapshot snapshot = findSnapshotOrThrow(nodeType, nodeKey);
		try {
			userKnowledgeNodeRepository.save(
					UserKnowledgeNode.forFirstClick(id, snapshot.label(), snapshot.topicCode(), now));
		} catch (DataIntegrityViolationException concurrentInsert) {
			// 동시 첫 클릭으로 다른 요청이 먼저 Row 를 만든 경우: 이제 존재하므로 갱신으로 되돌린다.
			userKnowledgeNodeRepository.incrementClick(id, now);
		}
		// 클릭 수가 바뀌었으니(0→1 첫 클릭 포함) 캐시된 참여도 집계를 지운다. 다음 조회가 다시 계산한다.
		exploredNodeCountCache.evict(userId);
	}

	private NodeSnapshot findSnapshotOrThrow(NodeType nodeType, String nodeKey) {
		Optional<NodeSnapshot> found;
		try {
			found = nodeSnapshotRepository.findSnapshot(nodeType, nodeKey);
		} catch (RuntimeException exception) {
			throw new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR);
		}
		return found.orElseThrow(() -> new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND));
	}
}

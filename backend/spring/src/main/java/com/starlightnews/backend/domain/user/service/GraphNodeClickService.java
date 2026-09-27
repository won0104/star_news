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
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 사용자가 그래프 Node 를 직접 클릭한 신호를 user_knowledge_nodes 에 기록한다.
 * 이미 가진 Node 면 클릭 수만 올리고(hot path 는 Neo4j 를 보지 않는다),
 * 없을 때만 Neo4j 스냅샷을 가져와 새 Row 를 만든다.
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

		// 존재 확인은 잠금을 잡지 않는 조회로 한다. 없는 행에 UPDATE 를 먼저 쳐서 알아내면
		// InnoDB 갭 락이 걸려 같은 Node 로 동시에 들어온 첫 클릭들이 데드락 난다.
		if (userKnowledgeNodeRepository.existsById(id)) {
			userKnowledgeNodeRepository.incrementClick(id, now);
			exploredNodeCountCache.evict(userId);
			return;
		}

		NodeSnapshot snapshot = findSnapshotOrThrow(nodeType, nodeKey);
		// 확인과 삽입 사이에 다른 요청이 먼저 만들었어도 Upsert 한 문장이 클릭 수 증가로 흡수한다.
		userKnowledgeNodeRepository.upsertClick(
				userId, nodeType.name(), nodeKey,
				UserKnowledgeNode.truncateLabel(snapshot.label()), snapshot.topicCode(), now);
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

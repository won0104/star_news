package com.starlightnews.backend.domain.user.repository;

import java.util.Optional;

import com.starlightnews.backend.global.enums.NodeType;

/**
 * 개인 Node 생성 시 참조할 Neo4j Node 스냅샷 조회 (읽기 전용).
 */
public interface NodeSnapshotRepository {

	/** Node 가 존재하면 표시 이름과 대표 Topic 을, 없으면 빈 Optional 을 반환한다. */
	Optional<NodeSnapshot> findSnapshot(NodeType nodeType, String nodeKey);
}

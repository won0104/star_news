package com.starlightnews.backend.domain.user.repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.global.enums.NodeType;

/**
 * 개인 Node 기록과 즐겨찾기 응답에 필요한 Neo4j Node 표시 정보 조회 (읽기 전용).
 */
public interface NodeSnapshotRepository {

	/** Node 가 존재하면 표시 이름과 대표 Topic 을, 없으면 빈 Optional 을 반환한다. */
	Optional<NodeSnapshot> findSnapshot(NodeType nodeType, String nodeKey);

	/** 한 유형의 Node ID 목록에 대응하는 화면 표시 이름을 일괄 조회한다. */
	List<NodeName> findNames(NodeType nodeType, Collection<String> nodeIds);
}

package com.starlightnews.backend.domain.graph.repository;

import java.util.Optional;

import com.starlightnews.backend.global.enums.NodeType;

/**
 * 지식 그래프 Node 조회 (Neo4j, 읽기 전용).
 */
public interface GraphNodeRepository {

	/**
	 * nodeType 에 해당하는 Label 과 업무 ID(nodeId)로 Node 를 조회한다.
	 * 해당 Label 의 Node 가 없으면 빈 Optional 을 반환한다.
	 */
	Optional<GraphNodeRecord> findNode(NodeType nodeType, String nodeKey);
}

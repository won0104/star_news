package com.starlightnews.backend.domain.graph.repository;

import java.util.Collection;
import java.util.List;

import com.starlightnews.backend.global.enums.NodeType;

/**
 * 중심 Node 주변의 Node·Edge 조회 (Neo4j, 읽기 전용).
 * 중심 Node 존재 확인·표시 이름은 {@link GraphNodeRepository} 를 재사용한다.
 */
public interface GraphNeighborRepository {

	/**
	 * 중심 Node 에서 depth Hop 이내로 연결된 주변 Node 를 neighborScore 순으로 조회한다.
	 * 반환 Node 유형은 EVENT·ENTITY·STATEMENT·TIME 으로 한정하며, 경로 중간 Node 도 같은 유형만 허용한다.
	 * neighborScore DESC, nodeType ASC, nodeKey ASC 로 정렬해 최대 fetchCap 개까지 가져온다.
	 */
	List<NeighborNode> findNeighbors(NodeType centerType, String centerKey, int depth, int fetchCap);

	/**
	 * 주어진 nodeKey 집합에 양 끝이 모두 포함되는 관계를 저장된 방향 그대로 조회한다.
	 */
	List<NeighborEdge> findEdges(Collection<String> nodeKeys);
}

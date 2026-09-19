package com.starlightnews.backend.domain.graph.repository;

/**
 * Neo4j 에서 조회한 Node 사이의 관계 한 개. 저장된 방향(source→target)을 그대로 유지하며,
 * weight 는 KG 추출 모델이 준 confidence(0~1)다. 비어 있으면 0.5 로 본다.
 * 양 끝 Node 의 nodeType 은 조회 요청 집합을 아는 서비스가 nodeKey 로 채운다.
 */
public record NeighborEdge(
		String sourceNodeKey,
		String targetNodeKey,
		String edgeType,
		double weight
) {
}

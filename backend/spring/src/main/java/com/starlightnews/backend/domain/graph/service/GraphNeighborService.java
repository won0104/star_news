package com.starlightnews.backend.domain.graph.service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

import com.starlightnews.backend.domain.graph.dto.GraphNeighborsResponse;
import com.starlightnews.backend.domain.graph.dto.GraphNeighborsResponse.Edge;
import com.starlightnews.backend.domain.graph.dto.GraphNeighborsResponse.NodeSummary;
import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.graph.repository.GraphNeighborRepository;
import com.starlightnews.backend.domain.graph.repository.GraphNodeRecord;
import com.starlightnews.backend.domain.graph.repository.GraphNodeRepository;
import com.starlightnews.backend.domain.graph.repository.NeighborEdge;
import com.starlightnews.backend.domain.graph.repository.NeighborNode;
import com.starlightnews.backend.domain.graph.support.NeighborCursor;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

/**
 * 중심 Node 주변의 Node·Edge 를 조회한다. Neo4j 단독(관계형 DB 미사용)이라 트랜잭션을 열지 않는다.
 * Neo4j 에서 스코어 매긴 이웃 전체(상한 {@link #NEIGHBOR_FETCH_CAP})를 받아 커서·limit 은 애플리케이션에서 자른다.
 */
@Service
@RequiredArgsConstructor
public class GraphNeighborService {

	/** Neo4j 에서 한 번에 가져올 이웃 상한. 커서 keyset 절단은 이 범위 안에서만 정확하다. */
	private static final int NEIGHBOR_FETCH_CAP = 300;

	private final GraphNodeRepository graphNodeRepository;
	private final GraphNeighborRepository graphNeighborRepository;

	/**
	 * 중심 Node 를 기준으로 depth Hop 이내 주변 Node 를 neighborScore 순으로, 그 사이 Edge 와 함께 반환한다.
	 * rawCursor 가 있으면 그 정렬 위치 다음부터, 최대 limit 개.
	 */
	public GraphNeighborsResponse getNeighbors(NodeType centerType, String centerKey, int depth, int limit,
			String rawCursor) {

		NeighborCursor cursor = (rawCursor == null || rawCursor.isBlank())
				? null : NeighborCursor.decode(rawCursor);

		GraphNodeRecord center = fromNeo4j(() -> graphNodeRepository.findNode(centerType, centerKey))
				.orElseThrow(() -> new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND));

		List<NeighborNode> scored = fromNeo4j(
				() -> graphNeighborRepository.findNeighbors(centerType, centerKey, depth, NEIGHBOR_FETCH_CAP));

		List<NeighborNode> afterCursor = (cursor == null)
				? scored
				: scored.stream().filter(node -> isAfterCursor(node, cursor)).toList();

		boolean hasNext = afterCursor.size() > limit;
		List<NeighborNode> page = hasNext ? List.copyOf(afterCursor.subList(0, limit)) : afterCursor;

		List<Edge> edges = resolveEdges(centerType, centerKey, page);
		String nextCursor = hasNext ? encodeCursor(page.get(page.size() - 1)) : null;

		NodeSummary centerNode = new NodeSummary(centerType.name(), centerKey, center.title());
		List<NodeSummary> nodes = page.stream()
				.map(node -> new NodeSummary(node.nodeType(), node.nodeKey(), node.label()))
				.toList();

		return new GraphNeighborsResponse(centerNode, nodes, edges, nodes.size(), hasNext, nextCursor);
	}

	/**
	 * 응답에 포함된 Node 집합(중심 + page) 안에서만 Edge 를 조회하고, 양 끝 nodeType 을 채운다.
	 * page 가 비면 Edge 도 없다.
	 */
	private List<Edge> resolveEdges(NodeType centerType, String centerKey, List<NeighborNode> page) {
		if (page.isEmpty()) {
			return List.of();
		}

		Map<String, String> typeByKey = new HashMap<>();
		typeByKey.put(centerKey, centerType.name());
		page.forEach(node -> typeByKey.put(node.nodeKey(), node.nodeType()));

		List<String> nodeKeys = new ArrayList<>(typeByKey.keySet());
		List<NeighborEdge> rawEdges = fromNeo4j(() -> graphNeighborRepository.findEdges(nodeKeys));

		return rawEdges.stream()
				.filter(edge -> typeByKey.containsKey(edge.sourceNodeKey())
						&& typeByKey.containsKey(edge.targetNodeKey()))
				.map(edge -> new Edge(
						typeByKey.get(edge.sourceNodeKey()), edge.sourceNodeKey(),
						typeByKey.get(edge.targetNodeKey()), edge.targetNodeKey(),
						edge.edgeType(), edge.weight()))
				.toList();
	}

	/** 정렬 기준 neighborScore DESC, nodeType ASC, nodeKey ASC 에서 cursor 위치보다 뒤인지. */
	private static boolean isAfterCursor(NeighborNode node, NeighborCursor cursor) {
		int byScore = Double.compare(node.neighborScore(), cursor.neighborScore());
		if (byScore != 0) {
			return byScore < 0;
		}
		int byType = node.nodeType().compareTo(cursor.nodeType());
		if (byType != 0) {
			return byType > 0;
		}
		return node.nodeKey().compareTo(cursor.nodeKey()) > 0;
	}

	private static String encodeCursor(NeighborNode node) {
		return new NeighborCursor(node.neighborScore(), node.nodeType(), node.nodeKey()).encode();
	}

	private <T> T fromNeo4j(Supplier<T> call) {
		try {
			return call.get();
		} catch (RuntimeException exception) {
			throw new BusinessException(GraphErrorCode.GRAPH_NODE_QUERY_FAILED);
		}
	}
}

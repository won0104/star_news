package com.starlightnews.backend.domain.graph.service;

import java.util.Optional;

import com.starlightnews.backend.domain.graph.dto.GraphNodeDetailResponse;
import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.graph.repository.GraphNodeRecord;
import com.starlightnews.backend.domain.graph.repository.GraphNodeRepository;
import com.starlightnews.backend.domain.user.domain.UserNodeFavoriteId;
import com.starlightnews.backend.domain.user.repository.UserNodeFavoriteRepository;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class GraphNodeService {

	private final GraphNodeRepository graphNodeRepository;
	private final UserNodeFavoriteRepository userNodeFavoriteRepository;

	/**
	 * 그래프 Node 상세를 조회한다.
	 * Neo4j 에서 표시 정보를, MySQL 에서 즐겨찾기 여부를 확인해 하나로 합친다.
	 * userId 가 null(비로그인)이면 bookmarked 는 항상 false 다.
	 */
	@Transactional(readOnly = true)
	public GraphNodeDetailResponse getNodeDetail(NodeType nodeType, String nodeKey, Long userId) {
		GraphNodeRecord node = findNodeOrThrow(nodeType, nodeKey);

		boolean bookmarked = userId != null
				&& userNodeFavoriteRepository.existsById(new UserNodeFavoriteId(userId, nodeType, nodeKey));

		return new GraphNodeDetailResponse(
				nodeType.name(), nodeKey, node.title(), node.type(), node.time(), bookmarked);
	}

	private GraphNodeRecord findNodeOrThrow(NodeType nodeType, String nodeKey) {
		Optional<GraphNodeRecord> found;
		try {
			found = graphNodeRepository.findNode(nodeType, nodeKey);
		} catch (RuntimeException exception) {
			throw new BusinessException(GraphErrorCode.GRAPH_NODE_QUERY_FAILED);
		}
		return found.orElseThrow(() -> new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND));
	}
}

package com.starlightnews.backend.domain.user.service;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Supplier;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.graph.repository.GraphNeighborRepository;
import com.starlightnews.backend.domain.graph.repository.NeighborEdge;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse.Edge;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse.Node;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse.TopicSummary;
import com.starlightnews.backend.domain.user.exception.PersonalGraphErrorCode;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 사용자가 읽은 기사·클릭으로 쌓인 개인 지식 그래프를 조회한다.
 * 개인 Node 포함 여부는 MySQL user_knowledge_nodes 가 기준이고, Node 사이 Edge 는 Neo4j 에서 조회해 조합한다.
 * Neo4j 조회로 개인 Node 후보를 새로 확장하지 않는다.
 */
@Service
@RequiredArgsConstructor
public class PersonalGraphService {

	/** DB DATETIME(6) 은 KST 벽시계로 저장되므로 응답 시각에 +09:00 오프셋을 붙인다. */
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	/** 개인 그래프 화면에 노출하는 Node 유형. */
	private static final Set<NodeType> DISPLAY_TYPES =
			EnumSet.of(NodeType.EVENT, NodeType.STORY, NodeType.ENTITY, NodeType.STATEMENT);

	private final UserKnowledgeNodeRepository userKnowledgeNodeRepository;
	private final GraphNeighborRepository graphNeighborRepository;

	/**
	 * 선택한 Topic 의 개인 Node·Edge 스냅샷을 반환한다.
	 * rawTopicCode 가 유효한 TopicCode 가 아니면 {@link PersonalGraphErrorCode#INVALID_TOPIC_CODE}.
	 */
	@Transactional(readOnly = true)
	public PersonalGraphMapResponse getTopicMap(Long userId, String rawTopicCode) {
		TopicCode topic = TopicCode.from(rawTopicCode)
				.orElseThrow(() -> new BusinessException(PersonalGraphErrorCode.INVALID_TOPIC_CODE));

		List<UserKnowledgeNode> rows = userKnowledgeNodeRepository
				.findByUserIdAndTopicCode(userId, topic.name()).stream()
				.filter(row -> DISPLAY_TYPES.contains(row.getId().getNodeType()))
				.toList();

		return new PersonalGraphMapResponse(
				OffsetDateTime.now(KST),
				new TopicSummary(topic.name(), topic.labelKo()),
				toNodes(rows),
				resolveEdges(rows));
	}

	private List<Node> toNodes(List<UserKnowledgeNode> rows) {
		if (rows.isEmpty()) {
			return List.of();
		}
		int maxImportance = rows.stream().mapToInt(PersonalGraphService::importance).max().orElse(1);
		return rows.stream()
				.map(row -> new Node(
						graphNodeId(row),
						row.getId().getNodeType().name(),
						row.getId().getNodeId(),
						row.getNodeLabel(),
						row.getReadArticleCount(),
						(double) importance(row) / maxImportance))
				.toList();
	}

	private List<Edge> resolveEdges(List<UserKnowledgeNode> rows) {
		if (rows.isEmpty()) {
			return List.of();
		}

		Map<String, String> typeByKey = rows.stream().collect(Collectors.toMap(
				row -> row.getId().getNodeId(),
				row -> row.getId().getNodeType().name(),
				(existing, duplicate) -> existing));

		List<NeighborEdge> rawEdges = fromNeo4j(
				() -> graphNeighborRepository.findEdges(List.copyOf(typeByKey.keySet())));

		return rawEdges.stream()
				.filter(edge -> typeByKey.containsKey(edge.sourceNodeKey())
						&& typeByKey.containsKey(edge.targetNodeKey()))
				.map(edge -> new Edge(
						typeByKey.get(edge.sourceNodeKey()) + ":" + edge.sourceNodeKey(),
						typeByKey.get(edge.targetNodeKey()) + ":" + edge.targetNodeKey(),
						edge.edgeType(),
						edge.weight()))
				.toList();
	}

	/** 사용자 기준 중요도 = 읽은 기사 수 + Node 클릭 수. 집합 최댓값으로 나눠 0~1 로 정규화한다(잠정). */
	private static int importance(UserKnowledgeNode row) {
		return row.getReadArticleCount() + row.getNodeClickCount();
	}

	private static String graphNodeId(UserKnowledgeNode row) {
		return row.getId().getNodeType().name() + ":" + row.getId().getNodeId();
	}

	private <T> T fromNeo4j(Supplier<T> call) {
		try {
			return call.get();
		} catch (RuntimeException exception) {
			throw new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR);
		}
	}
}

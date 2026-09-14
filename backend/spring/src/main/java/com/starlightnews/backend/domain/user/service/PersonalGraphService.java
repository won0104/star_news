package com.starlightnews.backend.domain.user.service;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Supplier;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.graph.repository.GraphNeighborRepository;
import com.starlightnews.backend.domain.graph.repository.NeighborEdge;
import com.starlightnews.backend.domain.user.cache.ExploredNodeCountCache;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse.Edge;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse.Node;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse.TopicSummary;
import com.starlightnews.backend.domain.user.dto.PersonalGraphSummaryResponse;
import com.starlightnews.backend.domain.user.exception.PersonalGraphErrorCode;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository.TopicReadCount;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository.TopicNodeCount;
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

	/**
	 * 개인 그래프 화면에 노출하는 Node 유형. Article 과 직접(1홉) 관계가 있는 유형만 포함한다.
	 */
	private static final Set<NodeType> DISPLAY_TYPES =
			EnumSet.of(NodeType.EVENT, NodeType.ENTITY, NodeType.STATEMENT);

	/** DISPLAY_TYPES 의 문자열 이름. 네이티브 쿼리(findTopRepresentatives)의 IN 절 바인딩용. */
	private static final Set<String> DISPLAY_TYPE_NAMES = DISPLAY_TYPES.stream()
			.map(Enum::name)
			.collect(Collectors.toUnmodifiableSet());

	/**
	 * Topic 별 대표 Node 최대 개수. (요약 조회용)
	 * 정렬 기준(중요도 DESC, 읽은 기사 수 DESC, nodeId ASC)은
	 * {@link UserKnowledgeNodeRepository#findTopRepresentatives} 의 DB 쿼리가 담당한다.
	 */
	private static final int REPRESENTATIVE_LIMIT = 5;

	private final UserKnowledgeNodeRepository userKnowledgeNodeRepository;
	private final ArticleReadRepository articleReadRepository;
	private final GraphNeighborRepository graphNeighborRepository;
	private final ExploredNodeCountCache exploredNodeCountCache;

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

		List<Edge> edges = findRealEdges(rows).stream()
				.map(edge -> new Edge(edge.sourceId(), edge.targetId(), edge.relationship(), edge.weight()))
				.toList();

		return new PersonalGraphMapResponse(
				OffsetDateTime.now(KST),
				new TopicSummary(topic.name(), topic.labelKo()),
				toMapNodes(rows),
				edges);
	}

	/**
	 * 내 읽기 최초 진입용 요약을 반환한다. 7개 Topic 전부를 Cluster 로 반환하며, 대표 Node(최대
	 * {@value #REPRESENTATIVE_LIMIT}개)가 없는 Topic 도 sourceArticleCount·weight 0 인 빈 Cluster 로 나온다.
	 * Topic 당 대표 Node 는 DB 에서 바로 상위 {@value #REPRESENTATIVE_LIMIT}개만 받는다 — 사용자의 전체
	 * 개인 Node 를 애플리케이션으로 끌어와 자바에서 정렬·절단하면 노드가 많은 사용자에서 급격히 느려진다.
	 */
	@Transactional(readOnly = true)
	public PersonalGraphSummaryResponse getSummary(Long userId) {
		Map<String, List<UserKnowledgeNode>> representativesByTopic = new LinkedHashMap<>();
		for (TopicCode topic : TopicCode.values()) {
			List<UserKnowledgeNode> top = userKnowledgeNodeRepository.findTopRepresentatives(
					userId, topic.name(), DISPLAY_TYPE_NAMES, REPRESENTATIVE_LIMIT);
			if (!top.isEmpty()) {
				representativesByTopic.put(topic.name(), top);
			}
		}
		List<UserKnowledgeNode> allRepresentatives = representativesByTopic.values().stream()
				.flatMap(List::stream)
				.toList();

		Map<String, Long> readCountByTopic = toReadCountMap(
				articleReadRepository.countReadArticlesByTopic(userId));

		Map<String, Long> exploredNodeCountByTopic = exploredNodeCountCache.get(userId)
				.orElseGet(() -> {
					Map<String, Long> computed = toCountMap(
							userKnowledgeNodeRepository.countExploredNodesByTopic(userId, DISPLAY_TYPES));
					exploredNodeCountCache.put(userId, computed);
					return computed;
				});
		Map<String, Long> engagementByTopic = new LinkedHashMap<>();
		for (TopicCode topic : TopicCode.values()) {
			String topicCode = topic.name();
			engagementByTopic.put(topicCode,
					readCountByTopic.getOrDefault(topicCode, 0L) + exploredNodeCountByTopic.getOrDefault(topicCode, 0L));
		}
		long maxClusterEngagement = engagementByTopic.values().stream()
				.mapToLong(Long::longValue).max().orElse(0L);
		int maxImportance = allRepresentatives.stream()
				.mapToInt(PersonalGraphService::importance).max().orElse(1);

		List<PersonalGraphSummaryResponse.Node> nodes = new ArrayList<>();
		List<PersonalGraphSummaryResponse.Edge> edges = new ArrayList<>();

		for (TopicCode topic : TopicCode.values()) {
			String topicCode = topic.name();
			long readCount = readCountByTopic.getOrDefault(topicCode, 0L);
			long engagement = engagementByTopic.get(topicCode);
			double clusterWeight = maxClusterEngagement == 0 ? 0.0 : (double) engagement / maxClusterEngagement;
			String clusterId = "topic:" + topicCode;

			nodes.add(new PersonalGraphSummaryResponse.Node(
					clusterId, "TOPIC_CLUSTER", null, null, topicCode, topic.labelKo(), null,
					(int) readCount, clusterWeight));

			for (UserKnowledgeNode row : representativesByTopic.getOrDefault(topicCode, List.of())) {
				String nodeId = graphNodeId(row);
				double nodeWeight = (double) importance(row) / maxImportance;
				nodes.add(new PersonalGraphSummaryResponse.Node(
						nodeId, "NODE", row.getId().getNodeType().name(), row.getId().getNodeId(), topicCode,
						row.getNodeLabel(), null, row.getReadArticleCount(), nodeWeight));
				edges.add(new PersonalGraphSummaryResponse.Edge(clusterId, nodeId, "BELONGS_TO_TOPIC", nodeWeight));
			}
		}

		edges.addAll(findRealEdges(allRepresentatives).stream()
				.map(edge -> new PersonalGraphSummaryResponse.Edge(
						edge.sourceId(), edge.targetId(), edge.relationship(), edge.weight()))
				.toList());

		return new PersonalGraphSummaryResponse(OffsetDateTime.now(KST), nodes, edges);
	}

	private List<Node> toMapNodes(List<UserKnowledgeNode> rows) {
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

	private Map<String, Long> toReadCountMap(List<TopicReadCount> counts) {
		return counts.stream()
				.collect(Collectors.toMap(TopicReadCount::getTopicCode, TopicReadCount::getCount));
	}

	private Map<String, Long> toCountMap(List<TopicNodeCount> counts) {
		return counts.stream()
				.collect(Collectors.toMap(TopicNodeCount::getTopicCode, TopicNodeCount::getCount));
	}

	/** 주어진 Node 집합 안에서만 Neo4j Edge 를 조회한다. Node 가 없으면 빈 목록. */
	private List<EdgeView> findRealEdges(List<UserKnowledgeNode> rows) {
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
				.map(edge -> new EdgeView(
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

	/** Neo4j 관계 하나를 DTO 로 옮기기 전 공용 형태. */
	private record EdgeView(String sourceId, String targetId, String relationship, double weight) {
	}
}

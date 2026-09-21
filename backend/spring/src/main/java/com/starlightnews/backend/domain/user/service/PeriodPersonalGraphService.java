package com.starlightnews.backend.domain.user.service;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.starlightnews.backend.domain.graph.repository.GraphNeighborRepository;
import com.starlightnews.backend.domain.graph.repository.NeighborEdge;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse;
import com.starlightnews.backend.domain.user.dto.PersonalGraphSummaryResponse;
import com.starlightnews.backend.domain.user.exception.PersonalGraphErrorCode;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository.GraphReadRow;
import com.starlightnews.backend.domain.user.repository.PeriodGraphNodeRef;
import com.starlightnews.backend.domain.user.repository.PeriodGraphNodeRepository;
import com.starlightnews.backend.domain.user.support.GraphReadPeriod;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** 기간 내 마지막으로 읽은 기사에서 개인 그래프를 재구성한다. 누적 Node 카운트는 사용하지 않는다. */
@Service
@RequiredArgsConstructor
public class PeriodPersonalGraphService {

	private static final ZoneOffset KST = ZoneOffset.ofHours(9);
	private static final int ARTICLE_BATCH_SIZE = 200;
	private static final int REPRESENTATIVE_LIMIT = 5;
	private static final Comparator<NodeCount> NODE_ORDER = Comparator
			.comparingInt(NodeCount::readCount).reversed()
			.thenComparing(node -> node.ref().nodeType().name())
			.thenComparing(node -> node.ref().nodeKey());

	private final ArticleReadRepository articleReadRepository;
	private final PeriodGraphNodeRepository periodGraphNodeRepository;
	private final GraphNeighborRepository graphNeighborRepository;

	@Transactional(readOnly = true)
	public PersonalGraphMapResponse getTopicMap(Long userId, String rawTopicCode, GraphReadPeriod period) {
		TopicCode topic = TopicCode.from(rawTopicCode)
				.orElseThrow(() -> new BusinessException(PersonalGraphErrorCode.INVALID_TOPIC_CODE));
		PeriodSnapshot snapshot = load(userId, period);
		List<NodeCount> selected = snapshot.nodes().values().stream()
				.filter(node -> topic.name().equals(node.ref().topicCode()))
				.sorted(NODE_ORDER)
				.toList();
		int maxCount = selected.stream().mapToInt(NodeCount::readCount).max().orElse(1);

		List<PersonalGraphMapResponse.Node> nodes = selected.stream()
				.map(node -> new PersonalGraphMapResponse.Node(
						id(node), node.ref().nodeType().name(), node.ref().nodeKey(), node.ref().label(),
						node.readCount(), (double) node.readCount() / maxCount))
				.toList();
		List<PersonalGraphMapResponse.Edge> edges = findRealEdges(selected).stream()
				.map(edge -> new PersonalGraphMapResponse.Edge(
						edge.sourceId(), edge.targetId(), edge.relationship(), edge.weight()))
				.toList();
		return new PersonalGraphMapResponse(OffsetDateTime.now(KST),
				new PersonalGraphMapResponse.TopicSummary(topic.name(), topic.labelKo()), nodes, edges);
	}

	@Transactional(readOnly = true)
	public PersonalGraphSummaryResponse getSummary(Long userId, GraphReadPeriod period) {
		PeriodSnapshot snapshot = load(userId, period);
		Map<String, List<NodeCount>> representatives = new LinkedHashMap<>();
		for (TopicCode topic : TopicCode.values()) {
			representatives.put(topic.name(), snapshot.nodes().values().stream()
					.filter(node -> topic.name().equals(node.ref().topicCode()))
					.sorted(NODE_ORDER)
					.limit(REPRESENTATIVE_LIMIT)
					.toList());
		}
		List<NodeCount> allRepresentatives = representatives.values().stream().flatMap(List::stream).toList();
		int maxNodeCount = allRepresentatives.stream().mapToInt(NodeCount::readCount).max().orElse(1);
		long maxTopicCount = snapshot.topicReadCounts().values().stream().mapToLong(Long::longValue).max().orElse(0);

		List<PersonalGraphSummaryResponse.Node> nodes = new ArrayList<>();
		List<PersonalGraphSummaryResponse.Edge> edges = new ArrayList<>();
		for (TopicCode topic : TopicCode.values()) {
			long topicCount = snapshot.topicReadCounts().getOrDefault(topic.name(), 0L);
			String clusterId = "topic:" + topic.name();
			nodes.add(new PersonalGraphSummaryResponse.Node(clusterId, "TOPIC_CLUSTER", null, null,
					topic.name(), topic.labelKo(), (int) topicCount,
					maxTopicCount == 0 ? 0.0 : (double) topicCount / maxTopicCount));
			for (NodeCount node : representatives.get(topic.name())) {
				double weight = (double) node.readCount() / maxNodeCount;
				nodes.add(new PersonalGraphSummaryResponse.Node(id(node), "NODE",
						node.ref().nodeType().name(), node.ref().nodeKey(), topic.name(),
						node.ref().label(), node.readCount(), weight));
				edges.add(new PersonalGraphSummaryResponse.Edge(clusterId, id(node), "BELONGS_TO_TOPIC", weight));
			}
		}
		edges.addAll(findRealEdges(allRepresentatives).stream()
				.map(edge -> new PersonalGraphSummaryResponse.Edge(
						edge.sourceId(), edge.targetId(), edge.relationship(), edge.weight()))
				.toList());
		return new PersonalGraphSummaryResponse(OffsetDateTime.now(KST), nodes, edges);
	}

	private PeriodSnapshot load(Long userId, GraphReadPeriod period) {
		List<GraphReadRow> reads = articleReadRepository.findGraphReadsInPeriod(
				userId, period.fromInclusive(), period.toExclusive());
		Map<String, Long> topicReadCounts = new LinkedHashMap<>();
		List<String> articleNodeKeys = new ArrayList<>();
		Set<String> seenArticleKeys = new HashSet<>();
		for (GraphReadRow read : reads) {
			if (read.getTopicCode() != null) {
				topicReadCounts.merge(read.getTopicCode(), 1L, Long::sum);
			}
			if (read.getArticleNodeKey() != null && seenArticleKeys.add(read.getArticleNodeKey())) {
				articleNodeKeys.add(read.getArticleNodeKey());
			}
		}

		Map<String, NodeCount> nodes = new LinkedHashMap<>();
		Set<ArticleNodePair> countedPairs = new HashSet<>();
		for (int start = 0; start < articleNodeKeys.size(); start += ARTICLE_BATCH_SIZE) {
			List<String> batch = articleNodeKeys.subList(start,
					Math.min(start + ARTICLE_BATCH_SIZE, articleNodeKeys.size()));
			for (PeriodGraphNodeRef ref : findConnectedNodes(batch)) {
				String nodeId = ref.nodeType().name() + ":" + ref.nodeKey();
				if (countedPairs.add(new ArticleNodePair(ref.articleNodeKey(), nodeId))) {
					nodes.computeIfAbsent(nodeId, ignored -> new NodeCount(ref)).increment();
				}
			}
		}
		return new PeriodSnapshot(topicReadCounts, nodes);
	}

	private List<PeriodGraphNodeRef> findConnectedNodes(List<String> articleNodeKeys) {
		try {
			return periodGraphNodeRepository.findConnectedNodes(articleNodeKeys);
		} catch (RuntimeException exception) {
			throw new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR);
		}
	}

	private List<EdgeView> findRealEdges(List<NodeCount> nodes) {
		if (nodes.isEmpty()) {
			return List.of();
		}
		Map<String, String> typeByKey = new LinkedHashMap<>();
		for (NodeCount node : nodes) {
			typeByKey.putIfAbsent(node.ref().nodeKey(), node.ref().nodeType().name());
		}
		List<NeighborEdge> rawEdges;
		try {
			rawEdges = graphNeighborRepository.findEdges(typeByKey.keySet());
		} catch (RuntimeException exception) {
			throw new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR);
		}
		return rawEdges.stream()
				.filter(edge -> typeByKey.containsKey(edge.sourceNodeKey())
						&& typeByKey.containsKey(edge.targetNodeKey()))
				.map(edge -> new EdgeView(
						typeByKey.get(edge.sourceNodeKey()) + ":" + edge.sourceNodeKey(),
						typeByKey.get(edge.targetNodeKey()) + ":" + edge.targetNodeKey(),
						edge.edgeType(), edge.weight()))
				.toList();
	}

	private static String id(NodeCount node) {
		return node.ref().nodeType().name() + ":" + node.ref().nodeKey();
	}

	private record ArticleNodePair(String articleNodeKey, String nodeId) {
	}

	private record PeriodSnapshot(Map<String, Long> topicReadCounts, Map<String, NodeCount> nodes) {
	}

	private record EdgeView(String sourceId, String targetId, String relationship, double weight) {
	}

	private static final class NodeCount {
		private final PeriodGraphNodeRef ref;
		private int readCount;

		private NodeCount(PeriodGraphNodeRef ref) {
			this.ref = ref;
		}

		private PeriodGraphNodeRef ref() {
			return ref;
		}

		private int readCount() {
			return readCount;
		}

		private void increment() {
			readCount++;
		}
	}
}

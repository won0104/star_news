package com.starlightnews.backend.domain.usergraph.service;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest.ConsumedEvent;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest.InterestNode;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest.UserGraphSyncUser;
import com.starlightnews.backend.domain.usergraph.repository.UserGraphAggregationRepository;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.NodeType;
import org.springframework.stereotype.Service;

/**
 * 사용자 묶음 하나를 User Graph 동기화 요청으로 조립한다.
 *
 * <p>호출자가 사용자 ID 를 나눠 주면 그 묶음만 조립한다. <b>한 사용자를 두 묶음으로 쪼개서는 안 된다.</b>
 * FastAPI 는 요청에 없는 관계를 지우므로, 같은 사용자를 나눠 보내면 뒤 요청이 앞 요청의 결과를 지운다.
 */
@Service
public class UserGraphRequestAssembler {

	/**
	 * 즐겨찾기 중 관심 관계로 보낼 Node 유형.
	 *
	 * <p>명세상 {@code INTERESTED_IN} 의 대상은 Entity·Topic·Story 다. Topic 은 즐겨찾기할 수 없어
	 * 관심 분야 설정에서 따로 채우고, Event 즐겨찾기는 소비 관계로 전달되므로 여기서 제외한다.
	 */
	private static final List<String> FAVORITE_INTEREST_NODE_TYPES =
			List.of(NodeType.ENTITY.name(), NodeType.STORY.name());

	/** 저장된 시각은 KST 기준이다. FastAPI 가 오프셋으로 해석할 수 있게 붙여서 보낸다. */
	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

	private final UserGraphAggregationRepository aggregationRepository;
	private final TopicNodeIdResolver topicNodeIdResolver;

	public UserGraphRequestAssembler(UserGraphAggregationRepository aggregationRepository,
			TopicNodeIdResolver topicNodeIdResolver) {
		this.aggregationRepository = aggregationRepository;
		this.topicNodeIdResolver = topicNodeIdResolver;
	}

	/**
	 * 사용자 ID 묶음으로 요청 본문을 만든다.
	 *
	 * <p>집계 대상이 하나도 없는 사용자도 빈 목록으로 포함한다. 관심을 모두 해제한 경우가 그렇게 보이는데,
	 * 빼 버리면 Neo4j 에 남은 예전 관계가 지워지지 않는다.
	 *
	 * @param aggregatedAt 회차 전체가 공유하는 집계 시각
	 */
	public UserGraphSyncRequest assemble(List<Long> userIds, OffsetDateTime aggregatedAt) {
		if (userIds.isEmpty()) {
			return new UserGraphSyncRequest(List.of(), aggregatedAt);
		}

		Map<Long, List<InterestNode>> favoriteNodes = favoriteInterestNodes(userIds);
		Map<Long, List<String>> interestTopics = topicCodes(userIds, InterestType.INTEREST);
		Map<Long, List<String>> dislikeTopics = topicCodes(userIds, InterestType.DISLIKE);
		Map<Long, List<ConsumedEvent>> consumedEvents = consumedEvents(userIds);

		List<UserGraphSyncUser> users = userIds.stream()
				.map(userId -> new UserGraphSyncUser(
						userId,
						interestNodes(favoriteNodes, interestTopics, userId),
						dislikeTopics.getOrDefault(userId, List.of()),
						consumedEvents.getOrDefault(userId, List.of())))
				.toList();

		return new UserGraphSyncRequest(users, aggregatedAt);
	}

	/** 즐겨찾기에서 온 Node 와 관심 분야에서 온 Topic 을 합친다. */
	private List<InterestNode> interestNodes(Map<Long, List<InterestNode>> favoriteNodes,
			Map<Long, List<String>> interestTopics, Long userId) {
		List<InterestNode> topicNodes = topicNodeIdResolver
				.toNodeIds(interestTopics.getOrDefault(userId, List.of()))
				.stream()
				.map(nodeId -> new InterestNode(NodeType.TOPIC.name(), nodeId))
				.toList();

		return java.util.stream.Stream
				.concat(favoriteNodes.getOrDefault(userId, List.of()).stream(), topicNodes.stream())
				.toList();
	}

	private Map<Long, List<InterestNode>> favoriteInterestNodes(Collection<Long> userIds) {
		return aggregationRepository.findFavoriteInterestNodes(userIds, FAVORITE_INTEREST_NODE_TYPES)
				.stream()
				.collect(Collectors.groupingBy(
						UserGraphAggregationRepository.InterestNodeRow::getUserId,
						Collectors.mapping(
								row -> new InterestNode(row.getNodeType(), row.getNodeId()),
								Collectors.toList())));
	}

	private Map<Long, List<String>> topicCodes(Collection<Long> userIds, InterestType interestType) {
		return aggregationRepository.findTopicPreferences(userIds, interestType.name())
				.stream()
				.collect(Collectors.groupingBy(
						UserGraphAggregationRepository.TopicPreferenceRow::getUserId,
						Collectors.mapping(
								UserGraphAggregationRepository.TopicPreferenceRow::getTopicCode,
								Collectors.toList())));
	}

	private Map<Long, List<ConsumedEvent>> consumedEvents(Collection<Long> userIds) {
		return aggregationRepository.findConsumedEvents(userIds)
				.stream()
				.collect(Collectors.groupingBy(
						UserGraphAggregationRepository.ConsumedEventRow::getUserId,
						Collectors.mapping(
								row -> new ConsumedEvent(
										row.getNodeId(),
										row.getClickCount(),
										withSeoulOffset(row.getLastSeenAt()),
										row.getFavorited() != null && row.getFavorited() != 0),
								Collectors.toList())));
	}

	private OffsetDateTime withSeoulOffset(LocalDateTime lastSeenAt) {
		return lastSeenAt.atZone(SEOUL).toOffsetDateTime();
	}
}

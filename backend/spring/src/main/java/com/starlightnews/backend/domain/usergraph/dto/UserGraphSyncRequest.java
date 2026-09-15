package com.starlightnews.backend.domain.usergraph.dto;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * {@code POST /internal/v1/user-graph/sync} 요청 본문.
 *
 * <p>사용자 여러 명을 한 요청에 묶어 보낸다.
 *
 * <p>{@code aggregatedAt} 은 이 집계 스냅샷을 계산한 시각이다. FastAPI 는 이 값이 Neo4j 에 기록된
 * 것보다 오래되면 반영을 건너뛰므로, 한 회차를 여러 요청으로 나눠 보내더라도 회차 전체가 같은 값을
 * 써야 한다. 요청마다 새로 찍으면 순서가 뒤집힐 때 최신 상태를 덮어쓴다.
 */
public record UserGraphSyncRequest(
		List<UserGraphSyncUser> users,
		OffsetDateTime aggregatedAt
) {

	/** 사용자 한 명의 집계 결과. */
	public record UserGraphSyncUser(
			Long userId,
			List<InterestNode> interestNodes,
			List<String> dislikeTopicCodes,
			List<ConsumedEvent> consumedEvents
	) {
	}

	/**
	 * {@code INTERESTED_IN} 으로 반영할 대상.
	 *
	 * <p>{@code nodeKey} 는 Topic 이라도 코드가 아니라 Neo4j nodeId(UUID)다.
	 */
	public record InterestNode(
			String nodeType,
			String nodeKey
	) {
	}

	/** {@code CONSUMED} 로 반영할 Event 별 소비 집계. */
	public record ConsumedEvent(
			String eventId,
			Integer count,
			OffsetDateTime lastViewedAt
	) {
	}
}

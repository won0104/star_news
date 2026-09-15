package com.starlightnews.backend.domain.usergraph.service;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest.ConsumedEvent;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest.InterestNode;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest.UserGraphSyncUser;
import com.starlightnews.backend.domain.usergraph.repository.UserGraphAggregationRepository;
import com.starlightnews.backend.domain.usergraph.repository.UserGraphAggregationRepository.ConsumedEventRow;
import com.starlightnews.backend.domain.usergraph.repository.UserGraphAggregationRepository.InterestNodeRow;
import com.starlightnews.backend.domain.usergraph.repository.UserGraphAggregationRepository.TopicPreferenceRow;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class UserGraphRequestAssemblerTest {

	private static final OffsetDateTime AGGREGATED_AT =
			OffsetDateTime.of(2026, 9, 15, 5, 0, 0, 0, ZoneOffset.ofHours(9));

	private static final String ENTITY_ID = "00000126-2001-4000-8000-000000000001";
	private static final String STORY_ID = "00000126-2002-4000-8000-000000000002";
	private static final String EVENT_ID = "00000126-2003-4000-8000-000000000003";
	private static final String TOPIC_NODE_ID = "00000126-2004-4000-8000-000000000004";

	@Mock
	private UserGraphAggregationRepository aggregationRepository;

	@Mock
	private TopicNodeIdResolver topicNodeIdResolver;

	private UserGraphRequestAssembler assembler;

	@BeforeEach
	void setUp() {
		assembler = new UserGraphRequestAssembler(aggregationRepository, topicNodeIdResolver);
	}

	private InterestNodeRow interestRow(long userId, String nodeType, String nodeId) {
		return new InterestNodeRow() {
			@Override
			public Long getUserId() {
				return userId;
			}

			@Override
			public String getNodeType() {
				return nodeType;
			}

			@Override
			public String getNodeId() {
				return nodeId;
			}
		};
	}

	private TopicPreferenceRow topicRow(long userId, String topicCode) {
		return new TopicPreferenceRow() {
			@Override
			public Long getUserId() {
				return userId;
			}

			@Override
			public String getTopicCode() {
				return topicCode;
			}
		};
	}

	private ConsumedEventRow eventRow(long userId, String nodeId, int clickCount, LocalDateTime lastSeenAt) {
		return new ConsumedEventRow() {
			@Override
			public Long getUserId() {
				return userId;
			}

			@Override
			public String getNodeId() {
				return nodeId;
			}

			@Override
			public Integer getClickCount() {
				return clickCount;
			}

			@Override
			public LocalDateTime getLastSeenAt() {
				return lastSeenAt;
			}
		};
	}

	/** 아무것도 없는 상태를 기본으로 깔고, 테스트마다 필요한 것만 덮어쓴다. */
	private void givenNothingStored() {
		given(aggregationRepository.findFavoriteInterestNodes(any(), any())).willReturn(List.of());
		given(aggregationRepository.findTopicPreferences(any(), anyString())).willReturn(List.of());
		given(aggregationRepository.findConsumedEvents(any())).willReturn(List.of());
	}

	@Test
	void 즐겨찾기_Node와_관심_Topic을_합쳐_관심_목록을_만든다() {
		given(aggregationRepository.findFavoriteInterestNodes(any(), any()))
				.willReturn(List.of(interestRow(1L, "ENTITY", ENTITY_ID), interestRow(1L, "STORY", STORY_ID)));
		given(aggregationRepository.findTopicPreferences(any(), eq("INTEREST")))
				.willReturn(List.of(topicRow(1L, "ECONOMY")));
		given(aggregationRepository.findTopicPreferences(any(), eq("DISLIKE"))).willReturn(List.of());
		given(aggregationRepository.findConsumedEvents(any())).willReturn(List.of());
		given(topicNodeIdResolver.toNodeIds(List.of("ECONOMY"))).willReturn(List.of(TOPIC_NODE_ID));

		List<InterestNode> interestNodes = assembler.assemble(List.of(1L), AGGREGATED_AT)
				.users().get(0).interestNodes();

		assertThat(interestNodes)
				.extracting(InterestNode::nodeType, InterestNode::nodeKey)
				.containsExactly(
						tuple("ENTITY", ENTITY_ID),
						tuple("STORY", STORY_ID),
						tuple("TOPIC", TOPIC_NODE_ID));
	}

	@Test
	void 비관심_Topic은_코드_그대로_보낸다() {
		// DISLIKES 는 FastAPI 가 topicCode 로 Topic 을 찾으므로 nodeId 변환이 필요 없다.
		given(aggregationRepository.findFavoriteInterestNodes(any(), any())).willReturn(List.of());
		given(aggregationRepository.findTopicPreferences(any(), eq("INTEREST"))).willReturn(List.of());
		given(aggregationRepository.findTopicPreferences(any(), eq("DISLIKE")))
				.willReturn(List.of(topicRow(1L, "SPORTS")));
		given(aggregationRepository.findConsumedEvents(any())).willReturn(List.of());

		assertThat(assembler.assemble(List.of(1L), AGGREGATED_AT).users().get(0).dislikeTopicCodes())
				.containsExactly("SPORTS");
	}

	@Test
	void 소비_Event의_시각에_KST_오프셋을_붙인다() {
		givenNothingStored();
		given(aggregationRepository.findConsumedEvents(any()))
				.willReturn(List.of(eventRow(1L, EVENT_ID, 3, LocalDateTime.of(2026, 9, 15, 4, 30))));

		assertThat(assembler.assemble(List.of(1L), AGGREGATED_AT).users().get(0).consumedEvents())
				.containsExactly(new ConsumedEvent(EVENT_ID, 3,
						OffsetDateTime.of(2026, 9, 15, 4, 30, 0, 0, ZoneOffset.ofHours(9))));
	}

	@Test
	void 사용자별로_각자의_데이터만_담는다() {
		given(aggregationRepository.findFavoriteInterestNodes(any(), any()))
				.willReturn(List.of(interestRow(1L, "ENTITY", ENTITY_ID), interestRow(2L, "STORY", STORY_ID)));
		given(aggregationRepository.findTopicPreferences(any(), anyString())).willReturn(List.of());
		given(aggregationRepository.findConsumedEvents(any())).willReturn(List.of());

		List<UserGraphSyncUser> users = assembler.assemble(List.of(1L, 2L), AGGREGATED_AT).users();

		assertThat(users).extracting(UserGraphSyncUser::userId).containsExactly(1L, 2L);
		assertThat(users.get(0).interestNodes()).containsExactly(new InterestNode("ENTITY", ENTITY_ID));
		assertThat(users.get(1).interestNodes()).containsExactly(new InterestNode("STORY", STORY_ID));
	}

	@Test
	void 집계할_것이_없는_사용자도_빈_목록으로_포함한다() {
		// 빼 버리면 Neo4j 에 남은 예전 관계가 지워지지 않는다.
		givenNothingStored();

		UserGraphSyncUser user = assembler.assemble(List.of(1L), AGGREGATED_AT).users().get(0);

		assertThat(user.userId()).isEqualTo(1L);
		assertThat(user.interestNodes()).isEmpty();
		assertThat(user.dislikeTopicCodes()).isEmpty();
		assertThat(user.consumedEvents()).isEmpty();
	}

	@Test
	void 집계_시각은_주어진_값을_그대로_쓴다() {
		// 회차를 여러 요청으로 나눠도 같은 값이어야 낙관적 락이 어긋나지 않는다.
		givenNothingStored();

		assertThat(assembler.assemble(List.of(1L), AGGREGATED_AT).aggregatedAt()).isEqualTo(AGGREGATED_AT);
	}

	@Test
	void 사용자가_많아도_조회_횟수는_늘지_않는다() {
		// 사용자마다 조회하면 그대로 N+1 이 된다.
		givenNothingStored();

		assembler.assemble(List.of(1L, 2L, 3L, 4L, 5L), AGGREGATED_AT);

		verify(aggregationRepository, times(1)).findFavoriteInterestNodes(any(), any());
		verify(aggregationRepository, times(2)).findTopicPreferences(any(), anyString());
		verify(aggregationRepository, times(1)).findConsumedEvents(any());
	}

	@Test
	void 대상이_없으면_빈_요청을_만들고_조회하지_않는다() {
		UserGraphSyncRequest request = assembler.assemble(List.of(), AGGREGATED_AT);

		assertThat(request.users()).isEmpty();
		assertThat(request.aggregatedAt()).isEqualTo(AGGREGATED_AT);
		verify(aggregationRepository, times(0)).findConsumedEvents(any());
	}
}

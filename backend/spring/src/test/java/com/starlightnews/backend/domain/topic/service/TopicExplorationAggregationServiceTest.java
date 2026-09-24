package com.starlightnews.backend.domain.topic.service;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.topic.domain.TopicExplorationEntry;
import com.starlightnews.backend.domain.topic.repository.TopicExplorationAggregationRepository;
import com.starlightnews.backend.domain.topic.repository.TopicExplorationCandidate;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.enums.TopicCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class TopicExplorationAggregationServiceTest {

	private static final OffsetDateTime AGGREGATION_AT = OffsetDateTime.of(
			2026, 9, 24, 5, 50, 0, 0, ZoneOffset.ofHours(9));
	private static final List<TopicCode> SUPPORTED_TOPICS = List.of(TopicCode.values());

	@Mock
	private TopicExplorationAggregationRepository topicExplorationAggregationRepository;

	@Mock
	private TopicExplorationPersistenceService topicExplorationPersistenceService;

	@InjectMocks
	private TopicExplorationAggregationService topicExplorationAggregationService;

	@Test
	void 최근_24시간_후보에_Topic별_독립_순위를_부여해_다음_정각_회차로_저장한다() {
		List<TopicExplorationCandidate> candidates = List.of(
				new TopicExplorationCandidate(TopicCode.ECONOMY, "economy-1", "경제 사건 1", 12),
				new TopicExplorationCandidate(TopicCode.ECONOMY, "economy-2", "경제 사건 2", 7),
				new TopicExplorationCandidate(TopicCode.SOCIETY, "society-1", "사회 사건 1", 5));
		given(topicExplorationAggregationRepository.findTopDistinctEventsByTopic(
				AGGREGATION_AT.minusHours(24), AGGREGATION_AT, SUPPORTED_TOPICS, 10))
				.willReturn(candidates);

		int savedCount = topicExplorationAggregationService.aggregate(AGGREGATION_AT);

		assertThat(savedCount).isEqualTo(3);
		@SuppressWarnings("unchecked")
		ArgumentCaptor<Map<TopicCode, List<TopicExplorationEntry>>> entriesCaptor =
				ArgumentCaptor.forClass(Map.class);
		verify(topicExplorationPersistenceService).replaceSnapshot(
				org.mockito.ArgumentMatchers.eq(LocalDateTime.of(2026, 9, 24, 6, 0)),
				entriesCaptor.capture());

		Map<TopicCode, List<TopicExplorationEntry>> saved = entriesCaptor.getValue();
		assertThat(saved).containsOnlyKeys(TopicCode.ECONOMY, TopicCode.SOCIETY);
		assertThat(saved.get(TopicCode.ECONOMY)).extracting(TopicExplorationEntry::getRank)
				.containsExactly(1, 2);
		assertThat(saved.get(TopicCode.SOCIETY)).extracting(TopicExplorationEntry::getRank)
				.containsExactly(1);
		assertThat(saved.values().stream().flatMap(List::stream).toList())
				.extracting(TopicExplorationEntry::getNodeType)
				.containsOnly(NodeType.EVENT);
	}

	@Test
	void 후보가_없으면_기존_결과를_유지한다() {
		given(topicExplorationAggregationRepository.findTopDistinctEventsByTopic(
				AGGREGATION_AT.minusHours(24), AGGREGATION_AT, SUPPORTED_TOPICS, 10))
				.willReturn(List.of());

		int savedCount = topicExplorationAggregationService.aggregate(AGGREGATION_AT);

		assertThat(savedCount).isZero();
		verify(topicExplorationPersistenceService, never()).replaceSnapshot(
				org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
	}

	@Test
	void UTC_기준_시각도_KST_17시50분_집계와_18시_공개로_저장한다() {
		OffsetDateTime utcAggregationAt = OffsetDateTime.parse("2026-09-24T08:50:00Z");
		given(topicExplorationAggregationRepository.findTopDistinctEventsByTopic(
				utcAggregationAt.minusHours(24), utcAggregationAt, SUPPORTED_TOPICS, 10))
				.willReturn(List.of(new TopicExplorationCandidate(
						TopicCode.ECONOMY, "economy-1", "경제 사건", 3)));

		topicExplorationAggregationService.aggregate(utcAggregationAt);

		verify(topicExplorationPersistenceService).replaceSnapshot(
				org.mockito.ArgumentMatchers.eq(LocalDateTime.of(2026, 9, 24, 18, 0)),
				org.mockito.ArgumentMatchers.any());
	}
}

package com.starlightnews.backend.domain.trend.service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.trend.domain.Trend;
import com.starlightnews.backend.domain.trend.repository.TrendAggregationRepository;
import com.starlightnews.backend.domain.trend.repository.TrendCandidate;
import com.starlightnews.backend.global.enums.NodeType;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class TrendAggregationServiceTest {

	private static final OffsetDateTime SNAPSHOT_AT = OffsetDateTime.of(
			2026, 9, 15, 6, 0, 0, 0, ZoneOffset.ofHours(9));

	@Mock
	private TrendAggregationRepository trendAggregationRepository;

	@Mock
	private TrendPersistenceService trendPersistenceService;

	@InjectMocks
	private TrendAggregationService trendAggregationService;

	@Test
	void 최근_24시간_후보에_순위를_부여해_저장한다() {
		List<TrendCandidate> candidates = List.of(
				new TrendCandidate("event-1", "첫 번째 사건", 12),
				new TrendCandidate("event-2", "두 번째 사건", 7));
		given(trendAggregationRepository.findTopDistinctEvents(
				SNAPSHOT_AT.minusHours(24), SNAPSHOT_AT, 10)).willReturn(candidates);

		int savedCount = trendAggregationService.aggregate(SNAPSHOT_AT);

		assertThat(savedCount).isEqualTo(2);
		@SuppressWarnings("unchecked")
		ArgumentCaptor<List<Trend>> trendsCaptor = ArgumentCaptor.forClass(List.class);
		verify(trendPersistenceService).replaceSnapshot(
				org.mockito.ArgumentMatchers.eq(LocalDateTime.of(2026, 9, 15, 6, 0)),
				trendsCaptor.capture());
		List<Trend> saved = trendsCaptor.getValue();
		assertThat(saved).extracting(Trend::getRank).containsExactly(1, 2);
		assertThat(saved).extracting(Trend::getNodeType).containsOnly(NodeType.EVENT);
		assertThat(saved).extracting(Trend::getNodeId).containsExactly("event-1", "event-2");
		assertThat(saved).extracting(Trend::getArticleCount).containsExactly(12, 7);
		assertThat(saved).extracting(Trend::getTrendScore)
				.containsExactly(BigDecimal.valueOf(12), BigDecimal.valueOf(7));
	}

	@Test
	void 후보가_없으면_기존_결과를_유지한다() {
		given(trendAggregationRepository.findTopDistinctEvents(
				SNAPSHOT_AT.minusHours(24), SNAPSHOT_AT, 10)).willReturn(List.of());

		int savedCount = trendAggregationService.aggregate(SNAPSHOT_AT);

		assertThat(savedCount).isZero();
		verify(trendPersistenceService, never()).replaceSnapshot(
				org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
	}

	@Test
	void 제목이_없는_후보는_저장하지_않는다() {
		given(trendAggregationRepository.findTopDistinctEvents(
				SNAPSHOT_AT.minusHours(24), SNAPSHOT_AT, 10))
				.willReturn(List.of(new TrendCandidate("event-1", " ", 3)));

		assertThatThrownBy(() -> trendAggregationService.aggregate(SNAPSHOT_AT))
				.isInstanceOf(IllegalStateException.class)
				.hasMessageContaining("nodeTitle");
		verify(trendPersistenceService, never()).replaceSnapshot(
				org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
	}

	@Test
	void 기사_수가_INT_범위를_넘으면_저장하지_않는다() {
		given(trendAggregationRepository.findTopDistinctEvents(
				SNAPSHOT_AT.minusHours(24), SNAPSHOT_AT, 10))
				.willReturn(List.of(new TrendCandidate(
						"event-1", "사건", (long)Integer.MAX_VALUE + 1)));

		assertThatThrownBy(() -> trendAggregationService.aggregate(SNAPSHOT_AT))
				.isInstanceOf(ArithmeticException.class);
		verify(trendPersistenceService, never()).replaceSnapshot(
				org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
	}
}

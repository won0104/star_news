package com.starlightnews.backend.domain.trend.scheduler;

import java.time.Clock;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.stream.Stream;

import com.starlightnews.backend.domain.trend.config.TrendProperties;
import com.starlightnews.backend.domain.trend.service.TrendAggregationService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class TrendAggregationSchedulerTest {

	private static final ZoneId KST = ZoneId.of("Asia/Seoul");
	private static final String CRON = "0 0 6,18 * * *";

	@Mock
	private TrendAggregationService trendAggregationService;

	@AfterEach
	void clearInterruptedStatus() {
		Thread.interrupted();
	}

	@ParameterizedTest
	@MethodSource("snapshotAtCases")
	void 실행_시각을_직전_집계_기준_시각으로_정규화한다(
			LocalDateTime currentTime,
			OffsetDateTime expectedSnapshotAt
	) {
		TrendAggregationScheduler scheduler = scheduler(currentTime, 3, Duration.ZERO);
		given(trendAggregationService.aggregate(expectedSnapshotAt)).willReturn(10);

		scheduler.aggregateTrends();

		verify(trendAggregationService).aggregate(expectedSnapshotAt);
	}

	@Test
	void 실패_후_성공하면_동일한_집계_기준_시각으로_재시도한다() {
		LocalDateTime currentTime = LocalDateTime.of(2026, 9, 15, 18, 2);
		TrendAggregationScheduler scheduler = scheduler(currentTime, 3, Duration.ZERO);
		given(trendAggregationService.aggregate(any(OffsetDateTime.class)))
				.willThrow(new IllegalStateException("일시적 실패"))
				.willReturn(10);

		scheduler.aggregateTrends();

		ArgumentCaptor<OffsetDateTime> snapshotAtCaptor = ArgumentCaptor.forClass(OffsetDateTime.class);
		verify(trendAggregationService, times(2)).aggregate(snapshotAtCaptor.capture());
		assertThat(snapshotAtCaptor.getAllValues())
				.containsExactly(
						OffsetDateTime.parse("2026-09-15T18:00:00+09:00"),
						OffsetDateTime.parse("2026-09-15T18:00:00+09:00"));
	}

	@Test
	void 계속_실패하면_최초_시도와_세_번의_재시도_후_종료한다() {
		TrendAggregationScheduler scheduler = scheduler(
				LocalDateTime.of(2026, 9, 15, 6, 0),
				3,
				Duration.ZERO);
		given(trendAggregationService.aggregate(any(OffsetDateTime.class)))
				.willThrow(new IllegalStateException("계속 실패"));

		assertThatCode(scheduler::aggregateTrends).doesNotThrowAnyException();

		verify(trendAggregationService, times(4))
				.aggregate(OffsetDateTime.parse("2026-09-15T06:00:00+09:00"));
	}

	@Test
	void 재시도_대기가_인터럽트되면_추가_시도_없이_종료하고_상태를_복원한다() {
		TrendAggregationScheduler scheduler = scheduler(
				LocalDateTime.of(2026, 9, 15, 6, 0),
				3,
				Duration.ofMinutes(1));
		given(trendAggregationService.aggregate(any(OffsetDateTime.class)))
				.willThrow(new IllegalStateException("집계 실패"));
		Thread.currentThread().interrupt();

		assertThatCode(scheduler::aggregateTrends).doesNotThrowAnyException();

		verify(trendAggregationService).aggregate(OffsetDateTime.parse("2026-09-15T06:00:00+09:00"));
		assertThat(Thread.currentThread().isInterrupted()).isTrue();
	}

	private TrendAggregationScheduler scheduler(
			LocalDateTime currentTime,
			int retryCount,
			Duration retryDelay
	) {
		Clock clock = Clock.fixed(currentTime.atZone(KST).toInstant(), KST);
		TrendProperties properties = new TrendProperties(CRON, retryCount, retryDelay);
		return new TrendAggregationScheduler(trendAggregationService, properties, clock);
	}

	private static Stream<Arguments> snapshotAtCases() {
		return Stream.of(
				Arguments.of(
						LocalDateTime.of(2026, 9, 15, 5, 59),
						OffsetDateTime.parse("2026-09-14T18:00:00+09:00")),
				Arguments.of(
						LocalDateTime.of(2026, 9, 15, 6, 0),
						OffsetDateTime.parse("2026-09-15T06:00:00+09:00")),
				Arguments.of(
						LocalDateTime.of(2026, 9, 15, 17, 59),
						OffsetDateTime.parse("2026-09-15T06:00:00+09:00")),
				Arguments.of(
						LocalDateTime.of(2026, 9, 15, 18, 0),
						OffsetDateTime.parse("2026-09-15T18:00:00+09:00")),
				Arguments.of(
						LocalDateTime.of(2026, 9, 15, 23, 59),
						OffsetDateTime.parse("2026-09-15T18:00:00+09:00"))
		);
	}
}

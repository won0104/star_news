package com.starlightnews.backend.domain.topic.scheduler;

import java.time.Clock;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.stream.Stream;

import com.starlightnews.backend.domain.topic.config.TopicExplorationProperties;
import com.starlightnews.backend.domain.topic.service.TopicExplorationAggregationService;
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
class TopicExplorationAggregationSchedulerTest {

	private static final ZoneId KST = ZoneId.of("Asia/Seoul");
	private static final String CRON = "0 50 5,17 * * *";

	@Mock
	private TopicExplorationAggregationService topicExplorationAggregationService;

	@ParameterizedTest
	@MethodSource("aggregationAtCases")
	void 실행_시각을_직전_집계_기준_시각으로_정규화한다(
			LocalDateTime currentTime,
			OffsetDateTime expectedAggregationAt
	) {
		TopicExplorationAggregationScheduler scheduler = scheduler(currentTime, 3, Duration.ZERO);
		given(topicExplorationAggregationService.aggregate(expectedAggregationAt)).willReturn(10);

		scheduler.aggregateTopicExplorationEntries();

		verify(topicExplorationAggregationService).aggregate(expectedAggregationAt);
	}

	@Test
	void 실패_후_성공하면_동일한_집계_기준_시각으로_재시도한다() {
		TopicExplorationAggregationScheduler scheduler = scheduler(
				LocalDateTime.of(2026, 9, 24, 18, 2), 3, Duration.ZERO);
		given(topicExplorationAggregationService.aggregate(any(OffsetDateTime.class)))
				.willThrow(new IllegalStateException("일시적 실패"))
				.willReturn(10);

		scheduler.aggregateTopicExplorationEntries();

		ArgumentCaptor<OffsetDateTime> aggregationAtCaptor = ArgumentCaptor.forClass(OffsetDateTime.class);
		verify(topicExplorationAggregationService, times(2)).aggregate(aggregationAtCaptor.capture());
		assertThat(aggregationAtCaptor.getAllValues()).containsExactly(
				OffsetDateTime.parse("2026-09-24T17:50:00+09:00"),
				OffsetDateTime.parse("2026-09-24T17:50:00+09:00"));
	}

	@Test
	void 계속_실패하면_최초_시도와_세_번의_재시도_후_종료한다() {
		TopicExplorationAggregationScheduler scheduler = scheduler(
				LocalDateTime.of(2026, 9, 24, 5, 50), 3, Duration.ZERO);
		given(topicExplorationAggregationService.aggregate(any(OffsetDateTime.class)))
				.willThrow(new IllegalStateException("계속 실패"));

		assertThatCode(scheduler::aggregateTopicExplorationEntries).doesNotThrowAnyException();

		verify(topicExplorationAggregationService, times(4))
				.aggregate(OffsetDateTime.parse("2026-09-24T05:50:00+09:00"));
	}

	private TopicExplorationAggregationScheduler scheduler(
			LocalDateTime currentTime,
			int retryCount,
			Duration retryDelay
	) {
		Clock clock = Clock.fixed(currentTime.atZone(KST).toInstant(), KST);
		TopicExplorationProperties properties = new TopicExplorationProperties(CRON, retryCount, retryDelay);
		return new TopicExplorationAggregationScheduler(
				topicExplorationAggregationService, properties, clock);
	}

	private static Stream<Arguments> aggregationAtCases() {
		return Stream.of(
				Arguments.of(
						LocalDateTime.of(2026, 9, 24, 5, 49),
						OffsetDateTime.parse("2026-09-23T17:50:00+09:00")),
				Arguments.of(
						LocalDateTime.of(2026, 9, 24, 5, 50),
						OffsetDateTime.parse("2026-09-24T05:50:00+09:00")),
				Arguments.of(
						LocalDateTime.of(2026, 9, 24, 17, 49),
						OffsetDateTime.parse("2026-09-24T05:50:00+09:00")),
				Arguments.of(
						LocalDateTime.of(2026, 9, 24, 17, 50),
						OffsetDateTime.parse("2026-09-24T17:50:00+09:00")),
				Arguments.of(
						LocalDateTime.of(2026, 9, 24, 23, 59),
						OffsetDateTime.parse("2026-09-24T17:50:00+09:00")));
	}
}

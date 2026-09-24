package com.starlightnews.backend.domain.topic.scheduler;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.concurrent.TimeUnit;

import com.starlightnews.backend.domain.topic.config.TopicExplorationProperties;
import com.starlightnews.backend.domain.topic.service.TopicExplorationAggregationService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 매일 05:50 및 17:50 KST에 집계하여 06:00 및 18:00 공개 회차를 준비한다.
 * 집계가 최종 실패하면 기존 Topic별 탐색 결과를 유지하고 실패 여부를 로그로 남긴다.
 */
@Slf4j
@Component
public class TopicExplorationAggregationScheduler {

	private static final ZoneId KST = ZoneId.of("Asia/Seoul");
	private static final LocalTime MORNING_AGGREGATION_TIME = LocalTime.of(5, 50);
	private static final LocalTime EVENING_AGGREGATION_TIME = LocalTime.of(17, 50);

	private final TopicExplorationAggregationService topicExplorationAggregationService;
	private final TopicExplorationProperties topicExplorationProperties;
	private final Clock topicExplorationClock;

	public TopicExplorationAggregationScheduler(
			TopicExplorationAggregationService topicExplorationAggregationService,
			TopicExplorationProperties topicExplorationProperties,
			@Qualifier("topicExplorationClock") Clock topicExplorationClock
	) {
		this.topicExplorationAggregationService = topicExplorationAggregationService;
		this.topicExplorationProperties = topicExplorationProperties;
		this.topicExplorationClock = topicExplorationClock;
	}

	@Scheduled(cron = "${app.topic-exploration.aggregate-cron}", zone = "Asia/Seoul")
	public void aggregateTopicExplorationEntries() {
		OffsetDateTime aggregationAt = resolveLatestAggregationAt();
		int maxAttempts = topicExplorationProperties.retryCount() + 1;
		long totalStartedAt = System.nanoTime();

		for (int attempt = 1; attempt <= maxAttempts; attempt++) {
			long attemptStartedAt = System.nanoTime();
			try {
				log.info(
						"Topic별 탐색 집계 시작: aggregationAt={}, attempt={}/{}",
						aggregationAt,
						attempt,
						maxAttempts);

				int savedCount = topicExplorationAggregationService.aggregate(aggregationAt);

				log.info(
						"Topic별 탐색 집계 스케줄 완료: aggregationAt={}, savedCount={}, attempt={}/{}, "
								+ "attemptDurationMs={}, totalDurationMs={}",
						aggregationAt,
						savedCount,
						attempt,
						maxAttempts,
						elapsedMillis(attemptStartedAt),
						elapsedMillis(totalStartedAt));
				return;
			} catch (RuntimeException exception) {
				long attemptDurationMs = elapsedMillis(attemptStartedAt);
				if (attempt == maxAttempts) {
					log.error(
							"Topic별 탐색 집계 최종 실패: aggregationAt={}, attempts={}, "
									+ "lastAttemptDurationMs={}, totalDurationMs={}",
							aggregationAt,
							maxAttempts,
							attemptDurationMs,
							elapsedMillis(totalStartedAt),
							exception);
					return;
				}

				log.warn(
						"Topic별 탐색 집계 실패, 재시도 예정: aggregationAt={}, attempt={}/{}, "
								+ "attemptDurationMs={}, retryDelay={}",
						aggregationAt,
						attempt,
						maxAttempts,
						attemptDurationMs,
						topicExplorationProperties.retryDelay(),
						exception);

				if (!waitUntilRetry()) {
					log.warn(
							"Topic별 탐색 집계 재시도 중단: aggregationAt={}, completedAttempts={}, totalDurationMs={}",
							aggregationAt,
							attempt,
							elapsedMillis(totalStartedAt));
					return;
				}
			}
		}
	}

	private OffsetDateTime resolveLatestAggregationAt() {
		ZonedDateTime now = ZonedDateTime.now(topicExplorationClock).withZoneSameInstant(KST);
		LocalDate aggregationDate = now.toLocalDate();
		LocalTime aggregationTime;

		if (!now.toLocalTime().isBefore(EVENING_AGGREGATION_TIME)) {
			aggregationTime = EVENING_AGGREGATION_TIME;
		} else if (!now.toLocalTime().isBefore(MORNING_AGGREGATION_TIME)) {
			aggregationTime = MORNING_AGGREGATION_TIME;
		} else {
			aggregationDate = aggregationDate.minusDays(1);
			aggregationTime = EVENING_AGGREGATION_TIME;
		}

		return ZonedDateTime.of(aggregationDate, aggregationTime, KST).toOffsetDateTime();
	}

	private boolean waitUntilRetry() {
		try {
			Thread.sleep(topicExplorationProperties.retryDelay().toMillis());
			return true;
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			log.warn("Topic별 탐색 집계 재시도 대기가 중단되었습니다.", exception);
			return false;
		}
	}

	private long elapsedMillis(long startedAt) {
		return TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - startedAt);
	}
}

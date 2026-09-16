package com.starlightnews.backend.domain.trend.scheduler;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.concurrent.TimeUnit;

import lombok.extern.slf4j.Slf4j;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import com.starlightnews.backend.domain.trend.config.TrendProperties;
import com.starlightnews.backend.domain.trend.service.TrendAggregationService;

/**
 * 매일 05:00 및 17:00 KST에 집계해 06:00 및 18:00부터 조회할 결과를 준비한다.
 *
 * <p>집계가 최종 실패하면 기존 트렌드를 유지하며, 실패 여부는 로그로 남긴다.</p>
 */
@Slf4j
@Component
public class TrendAggregationScheduler {

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    private static final LocalTime MORNING_AGGREGATION_TIME = LocalTime.of(5, 0);
    private static final LocalTime EVENING_AGGREGATION_TIME = LocalTime.of(17, 0);

    private final TrendAggregationService trendAggregationService;
    private final TrendProperties trendProperties;
    private final Clock trendClock;

    public TrendAggregationScheduler(
            TrendAggregationService trendAggregationService,
            TrendProperties trendProperties,
            @Qualifier("trendClock") Clock trendClock
    ) {
        this.trendAggregationService = trendAggregationService;
        this.trendProperties = trendProperties;
        this.trendClock = trendClock;
    }

    @Scheduled(cron = "${app.trend.aggregate-cron}", zone = "Asia/Seoul")
    public void aggregateTrends() {
        OffsetDateTime aggregationAt = resolveLatestAggregationAt();
        int maxAttempts = trendProperties.retryCount() + 1;
        long totalStartedAt = System.nanoTime();

        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            long attemptStartedAt = System.nanoTime();
            try {
                log.info(
                        "트렌드 집계 시작: aggregationAt={}, attempt={}/{}",
                        aggregationAt,
                        attempt,
                        maxAttempts
                );

                int savedCount = trendAggregationService.aggregate(aggregationAt);

                log.info(
                        "트렌드 집계 스케줄 완료: aggregationAt={}, savedCount={}, attempt={}/{}, "
                                + "attemptDurationMs={}, totalDurationMs={}",
                        aggregationAt,
                        savedCount,
                        attempt,
                        maxAttempts,
                        elapsedMillis(attemptStartedAt),
                        elapsedMillis(totalStartedAt)
                );
                return;
            } catch (RuntimeException exception) {
                long attemptDurationMs = elapsedMillis(attemptStartedAt);
                if (attempt == maxAttempts) {
                    log.error(
                            "트렌드 집계 최종 실패: aggregationAt={}, attempts={}, "
                                    + "lastAttemptDurationMs={}, totalDurationMs={}",
                            aggregationAt,
                            maxAttempts,
                            attemptDurationMs,
                            elapsedMillis(totalStartedAt),
                            exception
                    );
                    return;
                }

                log.warn(
                        "트렌드 집계 실패, 재시도 예정: aggregationAt={}, attempt={}/{}, "
                                + "attemptDurationMs={}, retryDelay={}",
                        aggregationAt,
                        attempt,
                        maxAttempts,
                        attemptDurationMs,
                        trendProperties.retryDelay(),
                        exception
                );

                if (!waitUntilRetry()) {
                    log.warn(
                            "트렌드 집계 재시도 중단: aggregationAt={}, completedAttempts={}, totalDurationMs={}",
                            aggregationAt,
                            attempt,
                            elapsedMillis(totalStartedAt)
                    );
                    return;
                }
            }
        }
    }

    private OffsetDateTime resolveLatestAggregationAt() {
        ZonedDateTime now = ZonedDateTime.now(trendClock).withZoneSameInstant(KST);
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
            Thread.sleep(trendProperties.retryDelay().toMillis());
            return true;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            log.warn("트렌드 집계 재시도 대기가 중단되었습니다.", exception);
            return false;
        }
    }

    private long elapsedMillis(long startedAt) {
        return TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - startedAt);
    }
}

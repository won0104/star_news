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
 * 매일 06:00 및 18:00 KST에 오늘의 트렌드를 집계한다.
 *
 * <p>집계가 최종 실패하면 기존 트렌드를 유지하며, 실패 여부는 로그로 남긴다.</p>
 */
@Slf4j
@Component
public class TrendAggregationScheduler {

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    private static final LocalTime MORNING_SNAPSHOT_TIME = LocalTime.of(6, 0);
    private static final LocalTime EVENING_SNAPSHOT_TIME = LocalTime.of(18, 0);

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
        OffsetDateTime snapshotAt = resolveLatestSnapshotAt();
        int maxAttempts = trendProperties.retryCount() + 1;
        long totalStartedAt = System.nanoTime();

        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            long attemptStartedAt = System.nanoTime();
            try {
                log.info(
                        "트렌드 집계 시작: snapshotAt={}, attempt={}/{}",
                        snapshotAt,
                        attempt,
                        maxAttempts
                );

                int savedCount = trendAggregationService.aggregate(snapshotAt);

                log.info(
                        "트렌드 집계 스케줄 완료: snapshotAt={}, savedCount={}, attempt={}/{}, "
                                + "attemptDurationMs={}, totalDurationMs={}",
                        snapshotAt,
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
                            "트렌드 집계 최종 실패: snapshotAt={}, attempts={}, "
                                    + "lastAttemptDurationMs={}, totalDurationMs={}",
                            snapshotAt,
                            maxAttempts,
                            attemptDurationMs,
                            elapsedMillis(totalStartedAt),
                            exception
                    );
                    return;
                }

                log.warn(
                        "트렌드 집계 실패, 재시도 예정: snapshotAt={}, attempt={}/{}, "
                                + "attemptDurationMs={}, retryDelay={}",
                        snapshotAt,
                        attempt,
                        maxAttempts,
                        attemptDurationMs,
                        trendProperties.retryDelay(),
                        exception
                );

                if (!waitUntilRetry()) {
                    log.warn(
                            "트렌드 집계 재시도 중단: snapshotAt={}, completedAttempts={}, totalDurationMs={}",
                            snapshotAt,
                            attempt,
                            elapsedMillis(totalStartedAt)
                    );
                    return;
                }
            }
        }
    }

    private OffsetDateTime resolveLatestSnapshotAt() {
        ZonedDateTime now = ZonedDateTime.now(trendClock).withZoneSameInstant(KST);
        LocalDate snapshotDate = now.toLocalDate();
        LocalTime snapshotTime;

        if (!now.toLocalTime().isBefore(EVENING_SNAPSHOT_TIME)) {
            snapshotTime = EVENING_SNAPSHOT_TIME;
        } else if (!now.toLocalTime().isBefore(MORNING_SNAPSHOT_TIME)) {
            snapshotTime = MORNING_SNAPSHOT_TIME;
        } else {
            snapshotDate = snapshotDate.minusDays(1);
            snapshotTime = EVENING_SNAPSHOT_TIME;
        }

        return ZonedDateTime.of(snapshotDate, snapshotTime, KST).toOffsetDateTime();
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

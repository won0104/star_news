package com.starlightnews.backend.domain.trend.config;

import java.time.Duration;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * 오늘의 트렌드 집계 스케줄과 재시도 정책을 정의한다.
 */
@Validated
@ConfigurationProperties(prefix = "app.trend")
public record TrendProperties(
        @NotBlank String aggregateCron,
        @Min(0) int retryCount,
        @NotNull Duration retryDelay
) {

    public TrendProperties {
        if (retryDelay != null && retryDelay.isNegative()) {
            throw new IllegalArgumentException("app.trend.retry-delay는 음수일 수 없습니다.");
        }
    }
}

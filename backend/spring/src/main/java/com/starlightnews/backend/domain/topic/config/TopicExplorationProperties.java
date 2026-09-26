package com.starlightnews.backend.domain.topic.config;

import java.time.Duration;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * Topic별 탐색 진입 Node 집계 스케줄과 재시도 정책을 정의한다.
 */
@Validated
@ConfigurationProperties(prefix = "app.topic-exploration")
public record TopicExplorationProperties(
		@NotBlank String aggregateCron,
		@Min(0) int retryCount,
		@NotNull Duration retryDelay
) {

	public TopicExplorationProperties {
		if (retryDelay != null && retryDelay.isNegative()) {
			throw new IllegalArgumentException("app.topic-exploration.retry-delay는 음수일 수 없습니다.");
		}
	}
}

package com.starlightnews.backend.domain.recommendation.service;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * 추천 회차 보관 설정.
 *
 * @param retentionDays 지난 회차를 며칠까지 남길지. 회차가 하루 두 번 쌓이므로 상한을 둔다
 */
@Validated
@ConfigurationProperties(prefix = "app.recommendation")
public record RecommendationRetentionProperties(
		@Min(1) @Max(90) int retentionDays
) {

	private static final int DEFAULT_RETENTION_DAYS = 7;

	public RecommendationRetentionProperties {
		retentionDays = retentionDays == 0 ? DEFAULT_RETENTION_DAYS : retentionDays;
	}
}

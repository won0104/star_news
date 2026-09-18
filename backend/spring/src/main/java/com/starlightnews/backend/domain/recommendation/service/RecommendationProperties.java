package com.starlightnews.backend.domain.recommendation.service;

import java.time.Duration;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * 추천 생성·저장 설정.
 *
 * @param retentionDays 지난 회차를 며칠까지 남길지. 회차가 하루 두 번 쌓이므로 상한을 둔다
 * @param chunkSize     한 요청에 담을 사용자 수
 * @param limitPerUser  사용자별로 받을 추천 Event 최대 개수
 * @param maxAttempts   묶음 하나를 회차 안에서 최대 몇 번 보낼지. 첫 시도를 포함한다
 * @param retryDelay    재시도 전에 기다릴 시간. FastAPI 가 잠깐 막혔을 때 바로 다시 부르면 또 실패한다
 */
@Validated
@ConfigurationProperties(prefix = "app.recommendation")
public record RecommendationProperties(
		@Min(1) @Max(90) int retentionDays,
		@Min(1) @Max(1000) int chunkSize,
		@Min(1) @Max(50) int limitPerUser,
		@Min(1) @Max(5) int maxAttempts,
		Duration retryDelay
) {

	private static final int DEFAULT_RETENTION_DAYS = 7;
	private static final int DEFAULT_CHUNK_SIZE = 100;
	private static final int DEFAULT_LIMIT_PER_USER = 10;
	private static final int DEFAULT_MAX_ATTEMPTS = 3;
	private static final Duration DEFAULT_RETRY_DELAY = Duration.ofSeconds(30);

	public RecommendationProperties {
		retentionDays = retentionDays == 0 ? DEFAULT_RETENTION_DAYS : retentionDays;
		chunkSize = chunkSize == 0 ? DEFAULT_CHUNK_SIZE : chunkSize;
		limitPerUser = limitPerUser == 0 ? DEFAULT_LIMIT_PER_USER : limitPerUser;
		maxAttempts = maxAttempts == 0 ? DEFAULT_MAX_ATTEMPTS : maxAttempts;
		retryDelay = retryDelay == null ? DEFAULT_RETRY_DELAY : retryDelay;
	}
}

package com.starlightnews.backend.domain.recommendation.service;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * 추천 가중치 재튜닝 설정.
 *
 * @param timeout FastAPI 가 그리드서치를 끝낼 때까지 기다릴 시간. 다른 내부 호출보다 훨씬 길다
 */
@Validated
@ConfigurationProperties(prefix = "app.recommendation.retune")
public record RecommendationRetuneProperties(Duration timeout) {

	private static final Duration DEFAULT_TIMEOUT = Duration.ofMinutes(5);

	public RecommendationRetuneProperties {
		timeout = timeout == null ? DEFAULT_TIMEOUT : timeout;
	}
}

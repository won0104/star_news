package com.starlightnews.backend.domain.article.analysis;

import java.time.Duration;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * 기사 AI 분석 설정.
 *
 * @param timeout     기사 한 건 분석을 기다리는 시간. FastAPI 가 AI 워커를 150초까지 기다리므로
 *                    그보다 길어야 한다. 짧으면 Spring 이 먼저 끊고 실패로 기록하는데, FastAPI 는
 *                    뒤에서 Neo4j 에 계속 써서 "실패로 알고 있는데 그래프에는 들어간" 기사가 생긴다
 * @param batchSize   한 회차에 분석할 최대 기사 수. 기사당 약 5초라 300건이면 25분 남짓이다
 * @param maxAttempts 일시 실패를 몇 번까지 다시 시도할지. 넘으면 FAILED 로 두고 더 부르지 않는다
 */
@Validated
@ConfigurationProperties(prefix = "app.article.analysis")
public record ArticleAnalysisProperties(
		@NotNull Duration timeout,
		@Min(1) @Max(1_000) int batchSize,
		@Min(1) @Max(10) int maxAttempts
) {
}

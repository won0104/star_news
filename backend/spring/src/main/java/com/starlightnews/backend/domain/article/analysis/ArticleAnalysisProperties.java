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
 * @param timeout                기사 한 건 분석을 기다리는 시간. FastAPI 가 AI 워커를 150초까지 기다리므로
 *                               그보다 길어야 한다. 짧으면 Spring 이 먼저 끊고 실패로 기록하는데, FastAPI 는
 *                               뒤에서 Neo4j 에 계속 써서 "실패로 알고 있는데 그래프에는 들어간" 기사가 생긴다
 * @param batchSize              한 회차에 분석할 최대 기사 수. 기사당 약 5초라 300건이면 25분 남짓이다
 * @param maxAttempts            일시 실패를 몇 번까지 다시 시도할지. 넘으면 FAILED 로 두고 더 부르지 않는다
 * @param timeBudget             한 회차가 새 기사를 시작할 수 있는 시간. 지나면 남은 기사는 다음 회차로 넘긴다.
 *                               타임아웃이 드문드문 섞이면 한 건에 수 분이 걸려 회차가 다음 정각을 넘긴다
 * @param maxConsecutiveFailures 연속으로 몇 건이 실패하면 회차를 멈출지. 연달아 실패하면 기사 탓이 아니라
 *                               AI 워커 장애일 가능성이 높다. 멈추지 않으면 장애 몇 시간 사이에 수백 건이
 *                               시도 횟수를 다 써 FAILED 가 된다
 */
@Validated
@ConfigurationProperties(prefix = "app.article.analysis")
public record ArticleAnalysisProperties(
		@NotNull Duration timeout,
		@Min(1) @Max(1_000) int batchSize,
		@Min(1) @Max(10) int maxAttempts,
		@NotNull Duration timeBudget,
		@Min(1) @Max(100) int maxConsecutiveFailures
) {
}

package com.starlightnews.backend.domain.article.config;

import java.time.Duration;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * 기사 요약 생성(GMS 호출) 횟수 제한.
 *
 * <p>요약 API 는 비로그인 화면(트렌드 패널)에서도 부르므로 공개로 두고, 대신 실제로 GMS 를 부르는
 * 요청만 센다. 이미 저장된 요약을 돌려주거나 다른 요청이 만드는 중(PROCESSING)이면 세지 않으므로,
 * 평범하게 읽는 사람은 한도에 닿을 일이 거의 없다. 기사 ID 를 훑으며 요약을 몰아 만드는 경우만 막힌다.
 *
 * @param window     횟수를 세는 고정 창
 * @param userLimit  로그인 사용자 한 명이 창 안에서 새로 만들 수 있는 요약 수
 * @param guestLimit 비로그인 요청이 IP 하나에서 창 안에 새로 만들 수 있는 요약 수.
 *                   여러 사람이 한 공인 IP 를 쓸 수 있지만, 읽는 기사 대부분은 이미 요약이 있다
 */
@Validated
@ConfigurationProperties(prefix = "app.article.summary.rate-limit")
public record ArticleSummaryRateLimitProperties(
		@NotNull Duration window,
		@Min(1) @Max(100_000) int userLimit,
		@Min(1) @Max(100_000) int guestLimit
) {

	@AssertTrue(message = "app.article.summary.rate-limit.window 는 0 보다 커야 합니다.")
	public boolean isWindowPositive() {
		return window == null || (!window.isZero() && !window.isNegative());
	}
}

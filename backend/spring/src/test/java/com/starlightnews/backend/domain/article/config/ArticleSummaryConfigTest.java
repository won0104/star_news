package com.starlightnews.backend.domain.article.config;

import java.time.Duration;

import com.starlightnews.backend.domain.article.service.ArticleSummaryRateLimiter;
import com.starlightnews.backend.global.ratelimit.InMemoryRateLimitStore;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.ConfigDataApplicationContextInitializer;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.assertj.core.api.Assertions.assertThat;

/** 실제 application.properties 로 요약 생성 횟수 제한이 묶이는지 확인한다. */
class ArticleSummaryConfigTest {

	private final ApplicationContextRunner runner = new ApplicationContextRunner()
			.withInitializer(new ConfigDataApplicationContextInitializer())
			.withPropertyValues("spring.profiles.active=test")
			.withUserConfiguration(
					ArticleSummaryConfig.class,
					ArticleSummaryRateLimiter.class,
					InMemoryRateLimitStore.class);

	@Test
	void 기본값은_한_시간에_로그인_40회_비로그인_IP당_20회다() {
		runner.run(context -> {
			assertThat(context).hasNotFailed();
			assertThat(context).hasSingleBean(ArticleSummaryRateLimiter.class);
			ArticleSummaryRateLimitProperties properties = context.getBean(ArticleSummaryRateLimitProperties.class);
			assertThat(properties.window()).isEqualTo(Duration.ofHours(1));
			assertThat(properties.userLimit()).isEqualTo(40);
			assertThat(properties.guestLimit()).isEqualTo(20);
		});
	}

	@Test
	void 창이_0이면_기동하지_않는다() {
		runner.withPropertyValues("app.article.summary.rate-limit.window=0s")
				.run(context -> assertThat(context).hasFailed());
	}
}

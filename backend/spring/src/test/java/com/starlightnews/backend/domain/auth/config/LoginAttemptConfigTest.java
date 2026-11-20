package com.starlightnews.backend.domain.auth.config;

import java.time.Duration;

import com.starlightnews.backend.domain.auth.service.LoginAttemptLimiter;
import com.starlightnews.backend.global.ratelimit.InMemoryRateLimitStore;
import com.starlightnews.backend.global.ratelimit.RateLimitStore;
import com.starlightnews.backend.global.ratelimit.RedisRateLimitStore;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.ConfigDataApplicationContextInitializer;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.data.redis.core.StringRedisTemplate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

/** 실제 application.properties 로 로그인 시도 제한이 묶이고, app.auth.store 로 저장소가 갈리는지 확인한다. */
class LoginAttemptConfigTest {

	private final ApplicationContextRunner runner = new ApplicationContextRunner()
			.withInitializer(new ConfigDataApplicationContextInitializer())
			.withPropertyValues("spring.profiles.active=test")
			.withBean(StringRedisTemplate.class, () -> mock(StringRedisTemplate.class))
			.withUserConfiguration(
					LoginAttemptConfig.class,
					LoginAttemptLimiter.class,
					InMemoryRateLimitStore.class,
					RedisRateLimitStore.class);

	@Test
	void 기본값은_5회_실패시_15분_잠금이고_IP는_15분에_30회다() {
		runner.run(context -> {
			assertThat(context).hasNotFailed();
			LoginAttemptProperties properties = context.getBean(LoginAttemptProperties.class);
			assertThat(properties.maxFailures()).isEqualTo(5);
			assertThat(properties.lockDuration()).isEqualTo(Duration.ofMinutes(15));
			assertThat(properties.ipMaxFailures()).isEqualTo(30);
			assertThat(properties.ipWindow()).isEqualTo(Duration.ofMinutes(15));
		});
	}

	@Test
	void 인증_저장소가_memory면_인메모리_횟수_저장소를_쓴다() {
		runner.withPropertyValues("app.auth.store=memory").run(context ->
				assertThat(context.getBean(RateLimitStore.class)).isInstanceOf(InMemoryRateLimitStore.class));
	}

	@Test
	void 인증_저장소가_redis면_Redis_횟수_저장소를_쓴다() {
		runner.withPropertyValues("app.auth.store=redis").run(context ->
				assertThat(context.getBean(RateLimitStore.class)).isInstanceOf(RedisRateLimitStore.class));
	}

	@Test
	void 잠금_시간이_0이면_기동하지_않는다() {
		runner.withPropertyValues("app.auth.login-attempt.lock-duration=0s")
				.run(context -> assertThat(context).hasFailed());
	}
}

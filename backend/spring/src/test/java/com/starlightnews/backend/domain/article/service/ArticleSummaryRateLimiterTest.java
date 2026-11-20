package com.starlightnews.backend.domain.article.service;

import java.time.Duration;

import com.starlightnews.backend.domain.article.config.ArticleSummaryRateLimitProperties;
import com.starlightnews.backend.domain.article.exception.ArticleErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.ratelimit.InMemoryRateLimitStore;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;

class ArticleSummaryRateLimiterTest {

	private static final int USER_LIMIT = 3;
	private static final int GUEST_LIMIT = 2;

	private final ArticleSummaryRateLimiter limiter = new ArticleSummaryRateLimiter(
			new InMemoryRateLimitStore(),
			new ArticleSummaryRateLimitProperties(Duration.ofHours(1), USER_LIMIT, GUEST_LIMIT));

	private static void assertRateLimited(Throwable thrown) {
		assertThat(thrown).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) thrown).getErrorCode()).isEqualTo(ArticleErrorCode.SUMMARY_RATE_LIMITED);
		assertThat(ArticleErrorCode.SUMMARY_RATE_LIMITED.getStatus().value()).isEqualTo(429);
	}

	@Test
	void 비로그인은_IP별로_한도까지_허용하고_넘으면_429로_막는다() {
		for (int i = 0; i < GUEST_LIMIT; i++) {
			limiter.acquire(null, "203.0.113.10");
		}

		assertRateLimited(catchThrowable(() -> limiter.acquire(null, "203.0.113.10")));
		// 다른 IP 는 따로 센다.
		limiter.acquire(null, "198.51.100.7");
	}

	@Test
	void 로그인_사용자는_IP와_상관없이_사용자별로_센다() {
		for (int i = 0; i < USER_LIMIT; i++) {
			limiter.acquire(7L, "203.0.113." + i);
		}

		assertRateLimited(catchThrowable(() -> limiter.acquire(7L, "198.51.100.7")));
	}

	@Test
	void 같은_IP의_비로그인_한도가_찼어도_로그인_사용자는_막지_않는다() {
		for (int i = 0; i < GUEST_LIMIT; i++) {
			limiter.acquire(null, "203.0.113.10");
		}

		limiter.acquire(7L, "203.0.113.10");
		limiter.acquire(8L, "203.0.113.10");
	}
}

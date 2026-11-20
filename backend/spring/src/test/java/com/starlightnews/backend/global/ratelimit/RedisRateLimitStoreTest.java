package com.starlightnews.backend.global.ratelimit;

import java.io.IOException;
import java.time.Duration;

import com.github.fppt.jedismock.RedisServer;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;

import static org.assertj.core.api.Assertions.assertThat;

class RedisRateLimitStoreTest {

	private static RedisServer server;
	private static LettuceConnectionFactory connectionFactory;
	private static StringRedisTemplate redis;

	private RedisRateLimitStore store;

	@BeforeAll
	static void startRedis() throws IOException {
		server = RedisServer.newRedisServer().start();
		connectionFactory = new LettuceConnectionFactory(server.getHost(), server.getBindPort());
		connectionFactory.afterPropertiesSet();
		redis = new StringRedisTemplate(connectionFactory);
		redis.afterPropertiesSet();
	}

	@AfterAll
	static void stopRedis() throws IOException {
		connectionFactory.destroy();
		server.stop();
	}

	@BeforeEach
	void setUp() {
		redis.getConnectionFactory().getConnection().serverCommands().flushAll();
		store = new RedisRateLimitStore(redis);
	}

	@Test
	void 고정_창으로_올리면_횟수가_쌓이고_만료는_처음에만_걸린다() {
		assertThat(store.incrementInWindow("k", Duration.ofMinutes(10))).isEqualTo(1);
		redis.expire("ratelimit:k", Duration.ofSeconds(30));

		assertThat(store.incrementInWindow("k", Duration.ofMinutes(10))).isEqualTo(2);
		assertThat(redis.getExpire("ratelimit:k")).isBetween(1L, 30L);
		assertThat(store.count("k")).isEqualTo(2);
	}

	@Test
	void 고정_창은_만료가_빠진_키에_만료를_다시_건다() {
		// 만료 없이 남은 키는 영영 0 으로 돌아가지 않는다(로그인이면 영구 잠금).
		redis.opsForValue().set("ratelimit:k", "3");

		assertThat(store.incrementInWindow("k", Duration.ofMinutes(10))).isEqualTo(4);
		assertThat(redis.getExpire("ratelimit:k")).isBetween(1L, 600L);
	}

	@Test
	void 연장_방식은_올릴_때마다_만료를_다시_건다() {
		store.incrementAndExtend("k", Duration.ofMinutes(15));
		redis.expire("ratelimit:k", Duration.ofSeconds(30));

		assertThat(store.incrementAndExtend("k", Duration.ofMinutes(15))).isEqualTo(2);
		assertThat(redis.getExpire("ratelimit:k")).isGreaterThan(30L);
	}

	@Test
	void 없는_키는_0이고_reset_하면_지워진다() {
		assertThat(store.count("k")).isZero();

		store.incrementInWindow("k", Duration.ofMinutes(1));
		store.reset("k");

		assertThat(store.count("k")).isZero();
		assertThat(redis.hasKey("ratelimit:k")).isFalse();
	}
}

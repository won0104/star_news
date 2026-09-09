package com.starlightnews.backend.global.security;

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

class RedisRefreshSessionStoreTest {

	private static final Duration TTL = Duration.ofMinutes(30);

	private static RedisServer server;
	private static LettuceConnectionFactory connectionFactory;
	private static StringRedisTemplate redis;

	private RedisRefreshSessionStore store;

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
		store = new RedisRefreshSessionStore(redis);
	}

	@Test
	void 저장한_세션을_세션ID로_조회한다() {
		store.save("sid-1", new RefreshSession(42L, "hash-1"), TTL);

		assertThat(store.find("sid-1")).contains(new RefreshSession(42L, "hash-1"));
	}

	@Test
	void 없는_세션ID를_조회하면_빈_Optional이다() {
		assertThat(store.find("nope")).isEmpty();
	}

	@Test
	void 삭제한_세션은_조회되지_않는다() {
		store.save("sid-1", new RefreshSession(1L, "hash-1"), TTL);

		store.delete("sid-1");

		assertThat(store.find("sid-1")).isEmpty();
	}

	@Test
	void 저장하면_TTL이_설정된다() {
		store.save("sid-1", new RefreshSession(1L, "hash-1"), TTL);

		assertThat(redis.getExpire("auth:refresh:sid-1")).isBetween(1L, 1800L);
	}

	@Test
	void deleteAllByUserId는_해당_사용자_세션만_지우고_삭제한_수를_반환한다() {
		store.save("a-1", new RefreshSession(1L, "h1"), TTL);
		store.save("a-2", new RefreshSession(1L, "h2"), TTL);
		store.save("b-1", new RefreshSession(2L, "h3"), TTL);

		int deleted = store.deleteAllByUserId(1L);

		assertThat(deleted).isEqualTo(2);
		assertThat(store.find("a-1")).isEmpty();
		assertThat(store.find("a-2")).isEmpty();
		assertThat(store.find("b-1")).contains(new RefreshSession(2L, "h3"));
	}

	@Test
	void deleteAllByUserId는_세션이_없으면_0을_반환한다() {
		assertThat(store.deleteAllByUserId(99L)).isZero();
	}
}

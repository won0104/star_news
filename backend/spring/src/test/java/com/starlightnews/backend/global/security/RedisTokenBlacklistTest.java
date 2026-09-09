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

class RedisTokenBlacklistTest {

	private static RedisServer server;
	private static LettuceConnectionFactory connectionFactory;
	private static StringRedisTemplate redis;

	private RedisTokenBlacklist blacklist;

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
		blacklist = new RedisTokenBlacklist(redis);
	}

	@Test
	void 등록한_jti는_블랙리스트로_조회된다() {
		blacklist.blacklist("jti-1", Duration.ofMinutes(30));

		assertThat(blacklist.isBlacklisted("jti-1")).isTrue();
	}

	@Test
	void 등록하지_않은_jti는_블랙리스트가_아니다() {
		assertThat(blacklist.isBlacklisted("unknown")).isFalse();
	}

	@Test
	void TTL이_0이하이면_등록하지_않는다() {
		blacklist.blacklist("jti-zero", Duration.ZERO);
		blacklist.blacklist("jti-neg", Duration.ofSeconds(-5));

		assertThat(blacklist.isBlacklisted("jti-zero")).isFalse();
		assertThat(blacklist.isBlacklisted("jti-neg")).isFalse();
	}

	@Test
	void 등록하면_남은_시간만큼_TTL이_설정된다() {
		blacklist.blacklist("jti-1", Duration.ofMinutes(30));

		assertThat(redis.getExpire("auth:bl:jti-1")).isBetween(1L, 1800L);
	}
}

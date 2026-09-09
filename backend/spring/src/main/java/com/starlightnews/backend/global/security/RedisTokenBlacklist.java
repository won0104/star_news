package com.starlightnews.backend.global.security;

import java.time.Duration;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/**
 * Redis 기반 Access Token 블랙리스트 (다중 인스턴스용).
 * 키: auth:bl:{jti}, TTL 은 Redis 가 자동 만료시킨다.
 * app.auth.store=redis 일 때 사용된다.
 */
@Component
@ConditionalOnProperty(name = "app.auth.store", havingValue = "redis")
public class RedisTokenBlacklist implements TokenBlacklist {

	private static final String KEY_PREFIX = "auth:bl:";

	private final StringRedisTemplate redis;

	public RedisTokenBlacklist(StringRedisTemplate redis) {
		this.redis = redis;
	}

	@Override
	public void blacklist(String jti, Duration ttl) {
		// 이미 만료된 토큰은 등록할 필요가 없다 (Redis 는 0 이하 TTL 을 거부한다).
		if (ttl.isZero() || ttl.isNegative()) {
			return;
		}
		redis.opsForValue().set(KEY_PREFIX + jti, "1", ttl);
	}

	@Override
	public boolean isBlacklisted(String jti) {
		return Boolean.TRUE.equals(redis.hasKey(KEY_PREFIX + jti));
	}
}

package com.starlightnews.backend.global.ratelimit;

import java.time.Duration;
import java.util.List;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.stereotype.Component;

/**
 * Redis 기반 횟수 저장소 (다중 인스턴스용).
 * 키: ratelimit:{key} → 정수, TTL 은 Redis 가 자동 만료시킨다.
 * app.auth.store=redis 일 때 사용된다.
 *
 * <p>INCR 와 PEXPIRE 를 스크립트 하나로 묶는다. 따로 보내면 그 사이에 연결이 끊겼을 때 만료 없는 키가
 * 남아, 그 키는 영영 0 으로 돌아가지 않는다(로그인이면 영구 잠금이 된다).
 */
@Component
@ConditionalOnProperty(name = "app.auth.store", havingValue = "redis")
public class RedisRateLimitStore implements RateLimitStore {

	private static final String KEY_PREFIX = "ratelimit:";

	/** 고정 창: 새 키(또는 만료가 빠진 키)에만 만료를 건다. */
	private static final RedisScript<Long> INCREMENT_IN_WINDOW_SCRIPT = new DefaultRedisScript<>("""
			local count = redis.call('INCR', KEYS[1])
			if redis.call('PTTL', KEYS[1]) < 0 then
			  redis.call('PEXPIRE', KEYS[1], ARGV[1])
			end
			return count
			""", Long.class);

	/** 연장: 올릴 때마다 만료를 다시 건다. */
	private static final RedisScript<Long> INCREMENT_AND_EXTEND_SCRIPT = new DefaultRedisScript<>("""
			local count = redis.call('INCR', KEYS[1])
			redis.call('PEXPIRE', KEYS[1], ARGV[1])
			return count
			""", Long.class);

	private final StringRedisTemplate redis;

	public RedisRateLimitStore(StringRedisTemplate redis) {
		this.redis = redis;
	}

	@Override
	public long incrementInWindow(String key, Duration window) {
		return execute(INCREMENT_IN_WINDOW_SCRIPT, key, window);
	}

	@Override
	public long incrementAndExtend(String key, Duration ttl) {
		return execute(INCREMENT_AND_EXTEND_SCRIPT, key, ttl);
	}

	@Override
	public long count(String key) {
		String value = redis.opsForValue().get(KEY_PREFIX + key);
		return value == null ? 0 : Long.parseLong(value);
	}

	@Override
	public void reset(String key) {
		redis.delete(KEY_PREFIX + key);
	}

	private long execute(RedisScript<Long> script, String key, Duration ttl) {
		Long count = redis.execute(script, List.of(KEY_PREFIX + key), String.valueOf(ttl.toMillis()));
		if (count == null) {
			throw new IllegalStateException("Redis 횟수 증가 결과가 없습니다. key=" + key);
		}
		return count;
	}
}

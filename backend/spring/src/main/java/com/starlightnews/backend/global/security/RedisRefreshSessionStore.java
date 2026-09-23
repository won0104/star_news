package com.starlightnews.backend.global.security;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.core.Cursor;
import org.springframework.data.redis.core.ScanOptions;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.stereotype.Component;

/**
 * Redis 기반 Refresh 세션 저장소 (다중 인스턴스용).
 * 키: auth:refresh:{sessionId} → Hash {userId, hash}, TTL 은 Redis 가 자동 만료시킨다.
 * app.auth.store=redis 일 때 사용된다.
 */
@Component
@ConditionalOnProperty(name = "app.auth.store", havingValue = "redis")
public class RedisRefreshSessionStore implements RefreshSessionStore {

	private static final String KEY_PREFIX = "auth:refresh:";
	private static final String FIELD_USER_ID = "userId";
	private static final String FIELD_HASH = "hash";
	private static final String ROTATION_NOT_FOUND = "NOT_FOUND";
	private static final String ROTATION_REUSED = "REUSED";
	private static final String ROTATION_SUCCESS_PREFIX = "ROTATED:";

	private static final RedisScript<Long> SAVE_SCRIPT = new DefaultRedisScript<>("""
			redis.call('HSET', KEYS[1], 'userId', ARGV[1], 'hash', ARGV[2])
			redis.call('PEXPIRE', KEYS[1], ARGV[3])
			return 1
			""", Long.class);

	private static final RedisScript<String> ROTATE_SCRIPT = new DefaultRedisScript<>("""
			local currentHash = redis.call('HGET', KEYS[1], 'hash')
			local userId = redis.call('HGET', KEYS[1], 'userId')
			if not currentHash or not userId then
			  redis.call('DEL', KEYS[1])
			  return 'NOT_FOUND'
			end
			if currentHash ~= ARGV[1] then
			  redis.call('DEL', KEYS[1])
			  return 'REUSED'
			end
			redis.call('HSET', KEYS[1], 'hash', ARGV[2])
			redis.call('PEXPIRE', KEYS[1], ARGV[3])
			return 'ROTATED:' .. userId
			""", String.class);

	private final StringRedisTemplate redis;

	public RedisRefreshSessionStore(StringRedisTemplate redis) {
		this.redis = redis;
	}

	@Override
	public void save(String sessionId, RefreshSession session, Duration ttl) {
		redis.execute(
				SAVE_SCRIPT,
				List.of(KEY_PREFIX + sessionId),
				String.valueOf(session.userId()),
				session.refreshTokenHash(),
				String.valueOf(ttl.toMillis()));
	}

	@Override
	public Optional<RefreshSession> find(String sessionId) {
		Map<Object, Object> entries = redis.opsForHash().entries(KEY_PREFIX + sessionId);
		if (entries.isEmpty()) {
			return Optional.empty();
		}
		return Optional.of(new RefreshSession(
				Long.valueOf((String) entries.get(FIELD_USER_ID)),
				(String) entries.get(FIELD_HASH)));
	}

	@Override
	public RefreshSessionRotationResult rotate(
			String sessionId,
			String expectedRefreshTokenHash,
			String newRefreshTokenHash,
			Duration ttl
	) {
		String result = redis.execute(
				ROTATE_SCRIPT,
				List.of(KEY_PREFIX + sessionId),
				expectedRefreshTokenHash,
				newRefreshTokenHash,
				String.valueOf(ttl.toMillis()));
		if (ROTATION_NOT_FOUND.equals(result)) {
			return RefreshSessionRotationResult.notFound();
		}
		if (ROTATION_REUSED.equals(result)) {
			return RefreshSessionRotationResult.reused();
		}
		if (result != null && result.startsWith(ROTATION_SUCCESS_PREFIX)) {
			return RefreshSessionRotationResult.rotated(
					Long.parseLong(result.substring(ROTATION_SUCCESS_PREFIX.length())));
		}
		throw new IllegalStateException("Unexpected refresh rotation result: " + result);
	}

	@Override
	public void delete(String sessionId) {
		redis.delete(KEY_PREFIX + sessionId);
	}

	@Override
	public int deleteAllByUserId(Long userId) {
		// 세션 수가 적어(RTR 로 사용자당 대개 1개) 전체 스캔으로 충분하다.
		// 규모가 커지면 auth:refresh:uidx:{userId} Set 인덱스로 교체한다.
		String target = String.valueOf(userId);
		int deleted = 0;
		try (Cursor<String> cursor = redis.scan(
				ScanOptions.scanOptions().match(KEY_PREFIX + "*").count(200).build())) {
			while (cursor.hasNext()) {
				String key = cursor.next();
				Object uid = redis.opsForHash().get(key, FIELD_USER_ID);
				if (target.equals(uid)) {
					redis.delete(key);
					deleted++;
				}
			}
		}
		return deleted;
	}
}

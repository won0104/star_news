package com.starlightnews.backend.global.security;

import java.time.Duration;
import java.util.Map;
import java.util.Optional;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.core.Cursor;
import org.springframework.data.redis.core.ScanOptions;
import org.springframework.data.redis.core.StringRedisTemplate;
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

	private final StringRedisTemplate redis;

	public RedisRefreshSessionStore(StringRedisTemplate redis) {
		this.redis = redis;
	}

	@Override
	public void save(String sessionId, RefreshSession session, Duration ttl) {
		String key = KEY_PREFIX + sessionId;
		redis.opsForHash().putAll(key, Map.of(
				FIELD_USER_ID, String.valueOf(session.userId()),
				FIELD_HASH, session.refreshTokenHash()));
		redis.expire(key, ttl);
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

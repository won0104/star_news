package com.starlightnews.backend.global.security;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicReference;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * 인메모리 Refresh 세션 저장소 (개발/단일 인스턴스용).
 * 앱을 재시작하면 세션이 사라지고, 인스턴스 간 공유되지 않는다.
 * app.auth.store=redis 이면 {@link RedisRefreshSessionStore} 로 교체된다.
 */
@Component
@ConditionalOnProperty(name = "app.auth.store", havingValue = "memory", matchIfMissing = true)
public class InMemoryRefreshSessionStore implements RefreshSessionStore {

	private record Entry(RefreshSession session, Instant expiresAt) {
		boolean isExpired(Instant now) {
			return !now.isBefore(expiresAt);
		}
	}

	private final ConcurrentHashMap<String, Entry> sessions = new ConcurrentHashMap<>();

	@Override
	public void save(String sessionId, RefreshSession session, Duration ttl) {
		sessions.put(sessionId, new Entry(session, Instant.now().plus(ttl)));
	}

	@Override
	public Optional<RefreshSession> find(String sessionId) {
		Entry entry = sessions.get(sessionId);
		if (entry == null) {
			return Optional.empty();
		}
		if (entry.isExpired(Instant.now())) {
			sessions.remove(sessionId, entry);
			return Optional.empty();
		}
		return Optional.of(entry.session());
	}

	@Override
	public RefreshSessionRotationResult rotate(
			String sessionId,
			String expectedRefreshTokenHash,
			String newRefreshTokenHash,
			Duration ttl
	) {
		Instant now = Instant.now();
		AtomicReference<RefreshSessionRotationResult> result =
				new AtomicReference<>(RefreshSessionRotationResult.notFound());
		sessions.compute(sessionId, (key, entry) -> {
			if (entry == null || entry.isExpired(now)) {
				return null;
			}
			if (!entry.session().refreshTokenHash().equals(expectedRefreshTokenHash)) {
				result.set(RefreshSessionRotationResult.reused());
				return null;
			}

			long userId = entry.session().userId();
			result.set(RefreshSessionRotationResult.rotated(userId));
			return new Entry(
					new RefreshSession(userId, newRefreshTokenHash),
					now.plus(ttl));
		});
		return result.get();
	}

	@Override
	public void delete(String sessionId) {
		sessions.remove(sessionId);
	}

	@Override
	public int deleteAllByUserId(Long userId) {
		int before = sessions.size();
		sessions.values().removeIf(entry -> entry.session().userId().equals(userId));
		return before - sessions.size();
	}
}

package com.starlightnews.backend.global.security;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Component;

/**
 * 인메모리 Refresh 세션 저장소 (개발/단일 인스턴스용).
 * 앱을 재시작하면 세션이 사라지고, 인스턴스 간 공유되지 않는다.
 * 운영에서 다중 인스턴스로 확장하려면 Redis 구현으로 교체해야 한다.
 */
@Component
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
	public void delete(String sessionId) {
		sessions.remove(sessionId);
	}
}

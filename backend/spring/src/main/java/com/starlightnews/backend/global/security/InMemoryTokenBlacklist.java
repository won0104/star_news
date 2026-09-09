package com.starlightnews.backend.global.security;

import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * 인메모리 Access Token 블랙리스트 (개발/단일 인스턴스용).
 * 조회 시점에 만료된 항목을 정리한다(lazy expiry).
 * app.auth.store=redis 이면 {@link RedisTokenBlacklist} 로 교체된다.
 */
@Component
@ConditionalOnProperty(name = "app.auth.store", havingValue = "memory", matchIfMissing = true)
public class InMemoryTokenBlacklist implements TokenBlacklist {

	private final ConcurrentHashMap<String, Instant> expiryByJti = new ConcurrentHashMap<>();

	@Override
	public void blacklist(String jti, Duration ttl) {
		expiryByJti.put(jti, Instant.now().plus(ttl));
	}

	@Override
	public boolean isBlacklisted(String jti) {
		Instant expiresAt = expiryByJti.get(jti);
		if (expiresAt == null) {
			return false;
		}
		if (!Instant.now().isBefore(expiresAt)) {
			expiryByJti.remove(jti, expiresAt);
			return false;
		}
		return true;
	}
}

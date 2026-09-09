package com.starlightnews.backend.global.security;

import java.time.Duration;

/**
 * 로그아웃한 Access Token 을 남은 만료 시간 동안 무효 처리하는 저장소.
 * (auth:blacklist:{jti}) 현재 구현은 인메모리이며 Redis 준비 후 교체한다.
 */
public interface TokenBlacklist {

	/** 해당 jti 의 Access Token 을 ttl 동안 블랙리스트에 등록한다. */
	void blacklist(String jti, Duration ttl);

	/** 블랙리스트에 등록돼 있는지(= 로그아웃된 토큰인지) 확인한다. */
	boolean isBlacklisted(String jti);
}

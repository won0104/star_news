package com.starlightnews.backend.global.security;

import java.time.Duration;
import java.util.Optional;

/**
 * Refresh Token 세션 저장소. 현재 구현은 인메모리이며, 인프라에 Redis 가 준비되면
 * 동일 인터페이스의 Redis 구현으로 교체한다. (auth:refresh:{sessionId})
 */
public interface RefreshSessionStore {

	/** 세션을 저장한다. ttl 이 지나면 자동으로 사라진다. */
	void save(String sessionId, RefreshSession session, Duration ttl);

	/** 세션을 조회한다. 없거나 만료됐으면 빈 Optional. */
	Optional<RefreshSession> find(String sessionId);

	/** 세션을 즉시 삭제한다. (로그아웃 / Refresh Token Rotation) */
	void delete(String sessionId);
}

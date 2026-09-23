package com.starlightnews.backend.global.security;

import java.time.Duration;
import java.util.Optional;

/**
 * Refresh Token 세션 저장소. 로컬·테스트는 인메모리, 운영은 Redis 구현을 사용한다.
 * 세션 ID는 한 로그인에서 이어지는 RT 계열을 식별한다. (auth:refresh:{sessionId})
 */
public interface RefreshSessionStore {

	/** 세션을 저장한다. ttl 이 지나면 자동으로 사라진다. */
	void save(String sessionId, RefreshSession session, Duration ttl);

	/** 세션을 조회한다. 없거나 만료됐으면 빈 Optional. */
	Optional<RefreshSession> find(String sessionId);

	/**
	 * 제시된 RT 해시가 현재 해시와 같으면 새 해시로 교체한다.
	 *
	 * <p>조회·비교·교체는 한 원자적 연산이어야 한다. 이미 교체된 RT가 다시 들어오면
	 * {@code REUSED}를 반환하고 해당 토큰 계열의 세션을 삭제한다.
	 */
	RefreshSessionRotationResult rotate(
			String sessionId,
			String expectedRefreshTokenHash,
			String newRefreshTokenHash,
			Duration ttl);

	/** 세션을 즉시 삭제한다. (로그아웃 / 계정 보안 처리) */
	void delete(String sessionId);

	/**
	 * 해당 사용자의 모든 Refresh 세션을 삭제한다. (회원 탈퇴 시 전체 기기 로그아웃)
	 * 삭제한 세션 수를 반환한다.
	 */
	int deleteAllByUserId(Long userId);
}

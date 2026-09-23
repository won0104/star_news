package com.starlightnews.backend.global.security;

/**
 * Refresh Token 계열에 저장하는 현재 상태.
 * refreshTokenHash 는 현재 유효한 RT 원문이 아니라 해시이며, 회전·재사용 감지에 쓴다.
 */
public record RefreshSession(
		Long userId,
		String refreshTokenHash
) {
}

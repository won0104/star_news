package com.starlightnews.backend.global.security;

/**
 * Refresh Token 세션에 저장하는 값.
 * refreshTokenHash 는 RT 원문이 아니라 해시이며, 재발급 시 제시된 RT 와 비교하는 용도다.
 */
public record RefreshSession(
		Long userId,
		String refreshTokenHash
) {
}

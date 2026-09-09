package com.starlightnews.backend.global.security;

import java.time.Instant;

/**
 * 검증된 Access Token 에서 꺼낸 값.
 */
public record AccessTokenPayload(
		long userId,
		String jti,
		Instant expiresAt
) {
}

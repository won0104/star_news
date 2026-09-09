package com.starlightnews.backend.global.security;

import java.time.Instant;

/**
 * 인증된 요청의 principal. JwtAuthenticationFilter 가 Access Token 에서 채운다.
 * 컨트롤러는 @AuthenticationPrincipal AuthenticatedUser 로 받는다.
 */
public record AuthenticatedUser(
		long userId,
		String jti,
		Instant accessTokenExpiresAt
) {
}

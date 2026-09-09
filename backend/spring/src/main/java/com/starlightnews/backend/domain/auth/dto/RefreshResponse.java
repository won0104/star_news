package com.starlightnews.backend.domain.auth.dto;

/**
 * 토큰 재발급 응답 body. 로그인과 달리 user 정보는 포함하지 않는다.
 */
public record RefreshResponse(
		String accessToken,
		String tokenType,
		long expiresIn
) {
}

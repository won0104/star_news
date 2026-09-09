package com.starlightnews.backend.domain.auth.dto;

/**
 * 로그인 응답 body. Refresh Token 은 이 body 가 아니라 HttpOnly Cookie 로 전달된다.
 */
public record LoginResponse(
		String accessToken,
		String tokenType,
		long expiresIn,
		UserSummary user
) {

	public record UserSummary(
			Long userId,
			String loginId,
			String nickname
	) {
	}
}

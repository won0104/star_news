package com.starlightnews.backend.domain.auth.dto;

/**
 * AuthService.login() 의 반환값. 컨트롤러가 response 는 응답 body 로,
 * refreshToken 은 Set-Cookie 로 나눠 내보낸다.
 */
public record LoginResult(
		LoginResponse response,
		String refreshToken,
		long refreshTokenMaxAgeSeconds
) {
}

package com.starlightnews.backend.domain.auth.dto;

/**
 * AuthService.refresh() 의 반환값. 컨트롤러가 response 는 body 로,
 * refreshToken 은 Set-Cookie 로 교체한다.
 */
public record RefreshResult(
		RefreshResponse response,
		String refreshToken,
		long refreshTokenMaxAgeSeconds
) {
}

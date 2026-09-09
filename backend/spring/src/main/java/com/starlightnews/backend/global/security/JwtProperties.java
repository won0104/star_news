package com.starlightnews.backend.global.security;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * JWT 서명 키와 토큰 만료 시간(ms). app.jwt.* 프로퍼티에 바인딩된다.
 */
@Validated
@ConfigurationProperties(prefix = "app.jwt")
public record JwtProperties(

		@NotBlank
		String secret,

		@Positive
		long accessTokenValidity,

		@Positive
		long refreshTokenValidity
) {
}

package com.starlightnews.backend.global.security;

import java.nio.charset.StandardCharsets;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * JWT 서명 키와 토큰 만료 시간(ms). app.jwt.* 프로퍼티에 바인딩된다.
 *
 * <p>서명 키는 기본값 없이 JWT_SECRET 으로만 받는다. 비어 있거나 짧으면 기동 단계에서 바로 실패시킨다.
 * 조용히 뜨게 두면 운영에서 환경변수를 빠뜨렸을 때 공개된 키나 추측 가능한 키로 토큰이 발급되고,
 * 그 사실을 아무도 모른 채 누구나 토큰을 위조할 수 있는 상태가 된다.
 *
 * @param secret               HS256 서명 키. UTF-8 기준 32바이트(256비트) 이상이어야 한다
 * @param accessTokenValidity  Access Token 만료 시간(ms)
 * @param refreshTokenValidity Refresh Token 만료 시간(ms)
 */
@Validated
@ConfigurationProperties(prefix = "app.jwt")
public record JwtProperties(

		@NotBlank(message = "JWT 서명 키(JWT_SECRET)가 설정되지 않았습니다.")
		String secret,

		@Positive
		long accessTokenValidity,

		@Positive
		long refreshTokenValidity
) {

	/** HS256 키의 최소 길이. RFC 7518 3.2 는 해시 출력 길이(256비트) 이상의 키를 요구한다. */
	public static final int MIN_SECRET_BYTES = 32;

	/**
	 * 서명 키가 HS256 에 충분히 긴지.
	 *
	 * <p>jjwt 도 짧은 키를 거부하지만 JwtProvider 를 만들 때 WeakKeyException 으로 터져 원인이 설정이라는
	 * 것을 알기 어렵다. 바인딩 검증에서 먼저 막아 어떤 설정이 문제인지 메시지에 남긴다.
	 * 비어 있는 경우는 {@code @NotBlank} 가 따로 알리므로 여기서는 통과시킨다.
	 */
	@AssertTrue(message = "JWT 서명 키(JWT_SECRET)는 HS256 을 위해 UTF-8 기준 32바이트 이상이어야 합니다.")
	public boolean isSecretLongEnough() {
		if (secret == null || secret.isBlank()) {
			return true;
		}
		return secret.getBytes(StandardCharsets.UTF_8).length >= MIN_SECRET_BYTES;
	}
}

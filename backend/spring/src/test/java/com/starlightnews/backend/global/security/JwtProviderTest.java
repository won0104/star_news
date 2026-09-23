package com.starlightnews.backend.global.security;

import java.time.Duration;
import java.time.Instant;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class JwtProviderTest {

	private static final String SECRET = "test-secret-please-be-at-least-32-bytes-long-0123456789";
	private static final long ACCESS_MS = 3_600_000L;
	private static final long REFRESH_MS = 1_209_600_000L;

	private JwtProvider jwtProvider;

	@BeforeEach
	void setUp() {
		jwtProvider = new JwtProvider(new JwtProperties(SECRET, ACCESS_MS, REFRESH_MS));
	}

	@Test
	void 액세스_토큰을_만들고_파싱하면_사용자ID와_jti가_보존된다() {
		String token = jwtProvider.createAccessToken(42L);

		AccessTokenPayload payload = jwtProvider.parseAccessToken(token);

		assertThat(payload.userId()).isEqualTo(42L);
		assertThat(payload.jti()).isNotBlank();
		assertThat(payload.expiresAt()).isAfter(Instant.now());
	}

	@Test
	void 액세스_토큰은_발급마다_jti가_다르다() {
		String first = jwtProvider.createAccessToken(1L);
		String second = jwtProvider.createAccessToken(1L);

		assertThat(jwtProvider.parseAccessToken(first).jti())
				.isNotEqualTo(jwtProvider.parseAccessToken(second).jti());
	}

	@Test
	void 리프레시_토큰을_만들고_파싱하면_세션ID가_보존된다() {
		String token = jwtProvider.createRefreshToken("session-abc");

		assertThat(jwtProvider.parseRefreshTokenSessionId(token)).isEqualTo("session-abc");
	}

	@Test
	void 같은_세션ID로_발급해도_리프레시_토큰은_매번_다르다() {
		String first = jwtProvider.createRefreshToken("session-abc");
		String second = jwtProvider.createRefreshToken("session-abc");

		assertThat(first).isNotEqualTo(second);
		assertThat(jwtProvider.parseRefreshTokenSessionId(first)).isEqualTo("session-abc");
		assertThat(jwtProvider.parseRefreshTokenSessionId(second)).isEqualTo("session-abc");
	}

	@Test
	void 만료된_토큰을_파싱하면_EXPIRED_예외가_발생한다() {
		JwtProvider alreadyExpired = new JwtProvider(new JwtProperties(SECRET, -1_000L, -1_000L));
		String token = alreadyExpired.createAccessToken(1L);

		assertThatThrownBy(() -> jwtProvider.parseAccessToken(token))
				.isInstanceOf(JwtValidationException.class)
				.extracting(exception -> ((JwtValidationException) exception).getReason())
				.isEqualTo(JwtValidationException.Reason.EXPIRED);
	}

	@Test
	void 변조된_토큰을_파싱하면_INVALID_예외가_발생한다() {
		String token = jwtProvider.createAccessToken(1L);
		String tampered = token.substring(0, token.length() - 3) + "abc";

		assertThatThrownBy(() -> jwtProvider.parseAccessToken(tampered))
				.isInstanceOf(JwtValidationException.class)
				.extracting(exception -> ((JwtValidationException) exception).getReason())
				.isEqualTo(JwtValidationException.Reason.INVALID);
	}

	@Test
	void 다른_비밀키로_서명된_토큰은_INVALID_예외가_발생한다() {
		JwtProvider other = new JwtProvider(
				new JwtProperties("another-secret-also-at-least-32-bytes-long-0123456789", ACCESS_MS, REFRESH_MS));
		String token = other.createAccessToken(1L);

		assertThatThrownBy(() -> jwtProvider.parseAccessToken(token))
				.isInstanceOf(JwtValidationException.class);
	}

	@Test
	void 형식이_아닌_문자열을_파싱하면_INVALID_예외가_발생한다() {
		assertThatThrownBy(() -> jwtProvider.parseAccessToken("not-a-jwt"))
				.isInstanceOf(JwtValidationException.class);
	}

	@Test
	void 액세스_토큰을_리프레시로_파싱하면_INVALID_예외가_발생한다() {
		String accessToken = jwtProvider.createAccessToken(1L);

		assertThatThrownBy(() -> jwtProvider.parseRefreshTokenSessionId(accessToken))
				.isInstanceOf(JwtValidationException.class);
	}

	@Test
	void 토큰_만료_시간을_Duration으로_제공한다() {
		assertThat(jwtProvider.accessTokenValidity()).isEqualTo(Duration.ofMillis(ACCESS_MS));
		assertThat(jwtProvider.refreshTokenValidity()).isEqualTo(Duration.ofMillis(REFRESH_MS));
	}
}

package com.starlightnews.backend.global.security;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;

import javax.crypto.SecretKey;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.stereotype.Component;

/**
 * Access / Refresh Token 을 발급하고 검증한다. HMAC-SHA 서명.
 */
@Component
public class JwtProvider {

	private static final String CLAIM_TYPE = "type";
	private static final String TYPE_ACCESS = "access";
	private static final String TYPE_REFRESH = "refresh";

	private final SecretKey key;
	private final long accessTokenValidityMs;
	private final long refreshTokenValidityMs;

	public JwtProvider(JwtProperties properties) {
		this.key = Keys.hmacShaKeyFor(properties.secret().getBytes(StandardCharsets.UTF_8));
		this.accessTokenValidityMs = properties.accessTokenValidity();
		this.refreshTokenValidityMs = properties.refreshTokenValidity();
	}

	public String createAccessToken(long userId) {
		Instant now = Instant.now();
		return Jwts.builder()
				.subject(String.valueOf(userId))
				.id(UUID.randomUUID().toString())
				.claim(CLAIM_TYPE, TYPE_ACCESS)
				.issuedAt(Date.from(now))
				.expiration(Date.from(now.plusMillis(accessTokenValidityMs)))
				.signWith(key)
				.compact();
	}

	public String createRefreshToken(String sessionId) {
		Instant now = Instant.now();
		return Jwts.builder()
				.subject(sessionId)
				.claim(CLAIM_TYPE, TYPE_REFRESH)
				.issuedAt(Date.from(now))
				.expiration(Date.from(now.plusMillis(refreshTokenValidityMs)))
				.signWith(key)
				.compact();
	}

	public AccessTokenPayload parseAccessToken(String token) {
		Claims claims = parse(token, TYPE_ACCESS);
		return new AccessTokenPayload(
				Long.parseLong(claims.getSubject()),
				claims.getId(),
				claims.getExpiration().toInstant());
	}

	public String parseRefreshTokenSessionId(String token) {
		return parse(token, TYPE_REFRESH).getSubject();
	}

	public Duration accessTokenValidity() {
		return Duration.ofMillis(accessTokenValidityMs);
	}

	public Duration refreshTokenValidity() {
		return Duration.ofMillis(refreshTokenValidityMs);
	}

	private Claims parse(String token, String expectedType) {
		try {
			Claims claims = Jwts.parser()
					.verifyWith(key)
					.build()
					.parseSignedClaims(token)
					.getPayload();
			if (!expectedType.equals(claims.get(CLAIM_TYPE, String.class))) {
				throw new JwtValidationException(JwtValidationException.Reason.INVALID,
						"토큰 종류가 올바르지 않습니다.", null);
			}
			return claims;
		} catch (ExpiredJwtException exception) {
			throw new JwtValidationException(JwtValidationException.Reason.EXPIRED,
					"만료된 토큰입니다.", exception);
		} catch (JwtException | IllegalArgumentException exception) {
			throw new JwtValidationException(JwtValidationException.Reason.INVALID,
					"유효하지 않은 토큰입니다.", exception);
		}
	}
}

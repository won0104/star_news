package com.starlightnews.backend.global.security;

import java.io.IOException;
import java.util.List;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Authorization: Bearer 토큰이 있으면 검증해서 SecurityContext 에 AuthenticatedUser 를 채운다.
 * - 토큰 없음 → 그냥 통과 (공개 엔드포인트면 OK, 보호 엔드포인트면 EntryPoint 가 401)
 * - 토큰 불량/만료/블랙리스트 → 인증 없이 통과하되 예외를 request 속성에 담아 EntryPoint 가 사유별로 응답
 */
public class JwtAuthenticationFilter extends OncePerRequestFilter {

	public static final String JWT_ERROR_ATTRIBUTE = "jwtValidationException";
	private static final String BEARER_PREFIX = "Bearer ";

	private final JwtProvider jwtProvider;
	private final TokenBlacklist tokenBlacklist;

	public JwtAuthenticationFilter(JwtProvider jwtProvider, TokenBlacklist tokenBlacklist) {
		this.jwtProvider = jwtProvider;
		this.tokenBlacklist = tokenBlacklist;
	}

	@Override
	protected void doFilterInternal(
			HttpServletRequest request,
			HttpServletResponse response,
			FilterChain filterChain
	) throws ServletException, IOException {
		String token = resolveToken(request);
		if (token != null) {
			try {
				authenticate(request, token);
			} catch (JwtValidationException exception) {
				SecurityContextHolder.clearContext();
				request.setAttribute(JWT_ERROR_ATTRIBUTE, exception);
			}
		}
		filterChain.doFilter(request, response);
	}

	private void authenticate(HttpServletRequest request, String token) {
		AccessTokenPayload payload = jwtProvider.parseAccessToken(token);
		if (tokenBlacklist.isBlacklisted(payload.jti())) {
			throw new JwtValidationException(
					JwtValidationException.Reason.INVALID, "로그아웃된 토큰입니다.", null);
		}

		// principal : 인증된 주체
		AuthenticatedUser principal = new AuthenticatedUser(
				payload.userId(), payload.jti(), payload.expiresAt());
		Authentication authentication =
				new UsernamePasswordAuthenticationToken(principal, null, List.of());
		SecurityContextHolder.getContext().setAuthentication(authentication);
	}

	private String resolveToken(HttpServletRequest request) {
		String header = request.getHeader(HttpHeaders.AUTHORIZATION);
		if (header != null && header.startsWith(BEARER_PREFIX)) {
			String token = header.substring(BEARER_PREFIX.length()).trim();
			return token.isEmpty() ? null : token;
		}
		return null;
	}
}

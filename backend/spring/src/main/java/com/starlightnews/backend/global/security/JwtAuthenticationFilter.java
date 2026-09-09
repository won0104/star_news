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
 * Authorization: Bearer 토큰이 있으면 검증해서 SecurityContext 에 인증 정보를 채운다.
 * 토큰이 없으면 그냥 통과시키고(공개 엔드포인트면 OK, 보호 엔드포인트면 EntryPoint 가 401),
 * 토큰이 잘못됐으면 예외를 request 속성에 담아 EntryPoint 가 사유별로 응답하게 한다.
 */
public class JwtAuthenticationFilter extends OncePerRequestFilter {

	public static final String JWT_ERROR_ATTRIBUTE = "jwtValidationException";
	private static final String BEARER_PREFIX = "Bearer ";

	private final JwtProvider jwtProvider;

	public JwtAuthenticationFilter(JwtProvider jwtProvider) {
		this.jwtProvider = jwtProvider;
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
				AccessTokenPayload payload = jwtProvider.parseAccessToken(token);
				Authentication authentication = new UsernamePasswordAuthenticationToken(
						payload.userId(), null, List.of());
				SecurityContextHolder.getContext().setAuthentication(authentication);
			} catch (JwtValidationException exception) {
				SecurityContextHolder.clearContext();
				request.setAttribute(JWT_ERROR_ATTRIBUTE, exception);
			}
		}
		filterChain.doFilter(request, response);
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

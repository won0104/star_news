package com.starlightnews.backend.global.security;

import java.time.Duration;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;

import static org.assertj.core.api.Assertions.assertThat;

class JwtAuthenticationFilterTest {

	private static final String SECRET = "test-secret-please-be-at-least-32-bytes-long-0123456789";

	private JwtProvider jwtProvider;
	private InMemoryTokenBlacklist tokenBlacklist;
	private JwtAuthenticationFilter filter;

	@BeforeEach
	void setUp() {
		jwtProvider = new JwtProvider(new JwtProperties(SECRET, 3_600_000L, 1_209_600_000L));
		tokenBlacklist = new InMemoryTokenBlacklist();
		filter = new JwtAuthenticationFilter(jwtProvider, tokenBlacklist);
	}

	@AfterEach
	void tearDown() {
		SecurityContextHolder.clearContext();
	}

	private AuthenticatedUser authenticatedPrincipal() {
		return (AuthenticatedUser) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
	}

	@Test
	void 유효한_토큰이_있으면_SecurityContext에_사용자_정보를_담는다() throws Exception {
		MockHttpServletRequest request = new MockHttpServletRequest();
		request.addHeader(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(42L));

		filter.doFilter(request, new MockHttpServletResponse(), new MockFilterChain());

		AuthenticatedUser principal = authenticatedPrincipal();
		assertThat(principal.userId()).isEqualTo(42L);
		assertThat(principal.jti()).isNotBlank();
		assertThat(principal.accessTokenExpiresAt()).isNotNull();
	}

	@Test
	void Authorization_헤더가_없으면_인증_없이_통과한다() throws Exception {
		MockFilterChain chain = new MockFilterChain();

		filter.doFilter(new MockHttpServletRequest(), new MockHttpServletResponse(), chain);

		assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
		assertThat(chain.getRequest()).isNotNull();
	}

	@Test
	void Bearer가_아닌_헤더는_무시한다() throws Exception {
		MockHttpServletRequest request = new MockHttpServletRequest();
		request.addHeader(HttpHeaders.AUTHORIZATION, "Basic abcdef");

		filter.doFilter(request, new MockHttpServletResponse(), new MockFilterChain());

		assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
	}

	@Test
	void 잘못된_토큰이면_인증을_비우고_예외를_request_속성에_담는다() throws Exception {
		MockHttpServletRequest request = new MockHttpServletRequest();
		request.addHeader(HttpHeaders.AUTHORIZATION, "Bearer not-a-real-token");
		MockFilterChain chain = new MockFilterChain();

		filter.doFilter(request, new MockHttpServletResponse(), chain);

		assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
		assertThat(request.getAttribute(JwtAuthenticationFilter.JWT_ERROR_ATTRIBUTE))
				.isInstanceOf(JwtValidationException.class);
		assertThat(chain.getRequest()).isNotNull();
	}

	@Test
	void 만료된_토큰이면_예외의_사유가_EXPIRED다() throws Exception {
		JwtProvider expiredIssuer = new JwtProvider(new JwtProperties(SECRET, -1_000L, -1_000L));
		MockHttpServletRequest request = new MockHttpServletRequest();
		request.addHeader(HttpHeaders.AUTHORIZATION, "Bearer " + expiredIssuer.createAccessToken(1L));

		filter.doFilter(request, new MockHttpServletResponse(), new MockFilterChain());

		JwtValidationException exception = (JwtValidationException)
				request.getAttribute(JwtAuthenticationFilter.JWT_ERROR_ATTRIBUTE);
		assertThat(exception.getReason()).isEqualTo(JwtValidationException.Reason.EXPIRED);
	}

	@Test
	void 블랙리스트에_등록된_토큰이면_인증하지_않는다() throws Exception {
		String token = jwtProvider.createAccessToken(1L);
		String jti = jwtProvider.parseAccessToken(token).jti();
		tokenBlacklist.blacklist(jti, Duration.ofMinutes(10));

		MockHttpServletRequest request = new MockHttpServletRequest();
		request.addHeader(HttpHeaders.AUTHORIZATION, "Bearer " + token);

		filter.doFilter(request, new MockHttpServletResponse(), new MockFilterChain());

		assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
		assertThat(request.getAttribute(JwtAuthenticationFilter.JWT_ERROR_ATTRIBUTE))
				.isInstanceOf(JwtValidationException.class);
	}
}

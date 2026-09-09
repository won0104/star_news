package com.starlightnews.backend.domain.auth;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.jayway.jsonpath.JsonPath;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.security.JwtProvider;
import com.starlightnews.backend.global.security.RefreshSessionStore;
import com.starlightnews.backend.global.security.TokenBlacklist;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.cookie;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class AuthTokenLifecycleIntegrationTest {

	private static final String SIGNUP_PATH = ApiPaths.API_V1 + "/auth/signup";
	private static final String LOGIN_PATH = ApiPaths.API_V1 + "/auth/login";
	private static final String REFRESH_PATH = ApiPaths.API_V1 + "/auth/refresh";
	private static final String LOGOUT_PATH = ApiPaths.API_V1 + "/auth/logout";
	private static final String PROBE_PATH = ApiPaths.API_V1 + "/_probe";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ObjectMapper objectMapper;

	@Autowired
	private JwtProvider jwtProvider;

	@Autowired
	private RefreshSessionStore refreshSessionStore;

	@Autowired
	private TokenBlacklist tokenBlacklist;

	private record Tokens(String accessToken, String refreshToken) {
	}

	private Tokens login(String loginId) throws Exception {
		String signupBody = objectMapper.writeValueAsString(Map.of(
				"loginId", loginId, "password", "password1234", "nickname", "별빛",
				"interestedTopicCodes", List.of(), "dislikedTopicCodes", List.of()));
		mockMvc.perform(post(SIGNUP_PATH).contentType(MediaType.APPLICATION_JSON).content(signupBody))
				.andExpect(status().isCreated());

		String loginBody = objectMapper.writeValueAsString(Map.of("loginId", loginId, "password", "password1234"));
		MvcResult result = mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON).content(loginBody))
				.andExpect(status().isOk())
				.andReturn();

		String accessToken = JsonPath.read(result.getResponse().getContentAsString(), "$.data.accessToken");
		String refreshToken = result.getResponse().getCookie("refreshToken").getValue();
		return new Tokens(accessToken, refreshToken);
	}

	private String refreshWith(String refreshToken) throws Exception {
		MvcResult result = mockMvc.perform(post(REFRESH_PATH).cookie(new Cookie("refreshToken", refreshToken)))
				.andExpect(status().isOk())
				.andReturn();
		return result.getResponse().getCookie("refreshToken").getValue();
	}

	@Test
	void refresh하면_새_AT와_새_RT를_받고_기존_세션은_교체된다() throws Exception {
		Tokens tokens = login("cycle_a");
		String oldSessionId = jwtProvider.parseRefreshTokenSessionId(tokens.refreshToken());

		MvcResult result = mockMvc.perform(post(REFRESH_PATH)
						.cookie(new Cookie("refreshToken", tokens.refreshToken())))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.accessToken").isString())
				.andExpect(jsonPath("$.data.tokenType").value("Bearer"))
				.andExpect(jsonPath("$.data.user").doesNotExist())
				.andReturn();

		String newAccessToken = JsonPath.read(result.getResponse().getContentAsString(), "$.data.accessToken");
		String newRefreshToken = result.getResponse().getCookie("refreshToken").getValue();

		assertThat(newAccessToken).isNotEqualTo(tokens.accessToken());
		assertThat(newRefreshToken).isNotEqualTo(tokens.refreshToken());

		String newSessionId = jwtProvider.parseRefreshTokenSessionId(newRefreshToken);
		assertThat(refreshSessionStore.find(oldSessionId)).isEmpty();
		assertThat(refreshSessionStore.find(newSessionId)).isPresent();
	}

	@Test
	void 이미_회전된_RT를_다시_쓰면_401이고_최신_RT는_유효하다() throws Exception {
		Tokens tokens = login("cycle_b");
		String rotatedRefreshToken = refreshWith(tokens.refreshToken());

		mockMvc.perform(post(REFRESH_PATH).cookie(new Cookie("refreshToken", tokens.refreshToken())))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("REFRESH_SESSION_NOT_FOUND"));

		mockMvc.perform(post(REFRESH_PATH).cookie(new Cookie("refreshToken", rotatedRefreshToken)))
				.andExpect(status().isOk());
	}

	@Test
	void 로그아웃하면_AT는_블랙리스트되고_RT_세션은_삭제되며_쿠키가_만료된다() throws Exception {
		Tokens tokens = login("cycle_c");
		String jti = jwtProvider.parseAccessToken(tokens.accessToken()).jti();
		String sessionId = jwtProvider.parseRefreshTokenSessionId(tokens.refreshToken());

		mockMvc.perform(post(LOGOUT_PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken())
						.cookie(new Cookie("refreshToken", tokens.refreshToken())))
				.andExpect(status().isNoContent())
				.andExpect(cookie().value("refreshToken", ""))
				.andExpect(cookie().maxAge("refreshToken", 0));

		assertThat(tokenBlacklist.isBlacklisted(jti)).isTrue();
		assertThat(refreshSessionStore.find(sessionId)).isEmpty();

		// 로그아웃한 AT 로 보호 경로 접근 → 401
		mockMvc.perform(get(PROBE_PATH).header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken()))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_ACCESS_TOKEN"));

		// 로그아웃한 RT 로 재발급 → 401
		mockMvc.perform(post(REFRESH_PATH).cookie(new Cookie("refreshToken", tokens.refreshToken())))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("REFRESH_SESSION_NOT_FOUND"));
	}

	@Test
	void 로그아웃은_인증이_필요하다() throws Exception {
		mockMvc.perform(post(LOGOUT_PATH))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"));
	}

	@Test
	void refresh는_RT_쿠키가_없으면_401이다() throws Exception {
		mockMvc.perform(post(REFRESH_PATH))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_REFRESH_TOKEN"));
	}
}

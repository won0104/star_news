package com.starlightnews.backend.domain.user;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.jayway.jsonpath.JsonPath;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.repository.UserRepository;
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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.cookie;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class WithdrawalIntegrationTest {

	private static final String SIGNUP_PATH = ApiPaths.API_V1 + "/auth/signup";
	private static final String LOGIN_PATH = ApiPaths.API_V1 + "/auth/login";
	private static final String REFRESH_PATH = ApiPaths.API_V1 + "/auth/refresh";
	private static final String WITHDRAWAL_PATH = ApiPaths.API_V1 + "/users/me";
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

	@Autowired
	private UserRepository userRepository;

	private record Tokens(String accessToken, String refreshToken) {
	}

	private Tokens signupAndLogin(String loginId) throws Exception {
		String signupBody = objectMapper.writeValueAsString(Map.of(
				"loginId", loginId, "password", "password1234", "nickname", "별빛",
				"interestedTopicCodes", List.of("ECONOMY", "IT_SCIENCE"), "dislikedTopicCodes", List.of()));
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

	private String withdrawalBody(String password) throws Exception {
		return objectMapper.writeValueAsString(Map.of("password", password));
	}

	@Test
	void 탈퇴하면_계정이_soft_delete되고_세션은_사라지며_AT는_블랙리스트되고_관심분야는_남는다() throws Exception {
		Tokens tokens = signupAndLogin("wd_a");
		String jti = jwtProvider.parseAccessToken(tokens.accessToken()).jti();
		String sessionId = jwtProvider.parseRefreshTokenSessionId(tokens.refreshToken());

		mockMvc.perform(delete(WITHDRAWAL_PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken())
						.contentType(MediaType.APPLICATION_JSON)
						.content(withdrawalBody("password1234")))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data").doesNotExist())
				.andExpect(jsonPath("$.meta.requestId").isString())
				.andExpect(cookie().value("refreshToken", ""))
				.andExpect(cookie().maxAge("refreshToken", 0));

		User user = userRepository.findByLoginId("wd_a").orElseThrow();
		assertThat(user.isDeleted()).isTrue();
		assertThat(user.getInterests()).hasSize(2);
		assertThat(refreshSessionStore.find(sessionId)).isEmpty();
		assertThat(tokenBlacklist.isBlacklisted(jti)).isTrue();
	}

	@Test
	void 탈퇴한_계정으로_로그인하면_403_USER_DELETED다() throws Exception {
		Tokens tokens = signupAndLogin("wd_b");

		mockMvc.perform(delete(WITHDRAWAL_PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken())
						.contentType(MediaType.APPLICATION_JSON)
						.content(withdrawalBody("password1234")))
				.andExpect(status().isOk());

		String loginBody = objectMapper.writeValueAsString(Map.of("loginId", "wd_b", "password", "password1234"));
		mockMvc.perform(post(LOGIN_PATH).contentType(MediaType.APPLICATION_JSON).content(loginBody))
				.andExpect(status().isForbidden())
				.andExpect(jsonPath("$.code").value("USER_DELETED"));
	}

	@Test
	void 탈퇴_후_기존_RT로_재발급하면_401이고_기존_AT로_보호경로_접근도_401이다() throws Exception {
		Tokens tokens = signupAndLogin("wd_c");

		mockMvc.perform(delete(WITHDRAWAL_PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken())
						.contentType(MediaType.APPLICATION_JSON)
						.content(withdrawalBody("password1234")))
				.andExpect(status().isOk());

		mockMvc.perform(post(REFRESH_PATH).cookie(new Cookie("refreshToken", tokens.refreshToken())))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("REFRESH_SESSION_NOT_FOUND"));

		mockMvc.perform(get(PROBE_PATH).header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken()))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_ACCESS_TOKEN"));
	}

	@Test
	void 비밀번호가_틀리면_401_INVALID_CREDENTIALS이고_계정은_유지된다() throws Exception {
		Tokens tokens = signupAndLogin("wd_d");

		mockMvc.perform(delete(WITHDRAWAL_PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken())
						.contentType(MediaType.APPLICATION_JSON)
						.content(withdrawalBody("wrong-password")))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"));

		assertThat(userRepository.findByLoginId("wd_d").orElseThrow().isDeleted()).isFalse();
	}

	@Test
	void 비밀번호를_누락하면_400_INVALID_INPUT_VALUE다() throws Exception {
		Tokens tokens = signupAndLogin("wd_e");

		mockMvc.perform(delete(WITHDRAWAL_PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken())
						.contentType(MediaType.APPLICATION_JSON)
						.content("{}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"))
				.andExpect(jsonPath("$.errors[*].field").value(org.hamcrest.Matchers.hasItems("password")));

		assertThat(userRepository.findByLoginId("wd_e").orElseThrow().isDeleted()).isFalse();
	}
}

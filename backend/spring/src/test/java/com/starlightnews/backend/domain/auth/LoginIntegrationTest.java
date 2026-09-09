package com.starlightnews.backend.domain.auth;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.jayway.jsonpath.JsonPath;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.security.JwtProvider;
import com.starlightnews.backend.global.security.RefreshSession;
import com.starlightnews.backend.global.security.RefreshSessionStore;
import com.starlightnews.backend.global.security.TokenHasher;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class LoginIntegrationTest {

	private static final String SIGNUP_PATH = ApiPaths.API_V1 + "/auth/signup";
	private static final String LOGIN_PATH = ApiPaths.API_V1 + "/auth/login";
	private static final String LOGIN_ID = "starlight01";
	private static final String PASSWORD = "password1234";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ObjectMapper objectMapper;

	@Autowired
	private UserRepository userRepository;

	@Autowired
	private JwtProvider jwtProvider;

	@Autowired
	private RefreshSessionStore refreshSessionStore;

	private void signup() throws Exception {
		String body = objectMapper.writeValueAsString(Map.of(
				"loginId", LOGIN_ID,
				"password", PASSWORD,
				"nickname", "별빛",
				"interestedTopicCodes", List.of(),
				"dislikedTopicCodes", List.of()));
		mockMvc.perform(post(SIGNUP_PATH).contentType(MediaType.APPLICATION_JSON).content(body))
				.andExpect(status().isCreated());
	}

	private String loginBody(String loginId, String password) throws Exception {
		return objectMapper.writeValueAsString(Map.of("loginId", loginId, "password", password));
	}

	@Test
	void 회원가입한_계정으로_로그인하면_토큰과_쿠키를_받고_Refresh_세션이_저장된다() throws Exception {
		signup();
		Long userId = userRepository.findByLoginId(LOGIN_ID).orElseThrow().getId();

		MvcResult result = mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(loginBody(LOGIN_ID, PASSWORD)))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.tokenType").value("Bearer"))
				.andExpect(jsonPath("$.data.user.userId").value(userId))
				.andExpect(jsonPath("$.data.user.loginId").value(LOGIN_ID))
				.andExpect(jsonPath("$.data.user.nickname").value("별빛"))
				.andExpect(jsonPath("$.meta.requestId").isString())
				.andReturn();

		String accessToken = JsonPath.read(result.getResponse().getContentAsString(), "$.data.accessToken");
		assertThat(jwtProvider.parseAccessToken(accessToken).userId()).isEqualTo(userId);

		Cookie refreshCookie = result.getResponse().getCookie("refreshToken");
		assertThat(refreshCookie).isNotNull();
		assertThat(refreshCookie.isHttpOnly()).isTrue();

		String refreshToken = refreshCookie.getValue();
		String sessionId = jwtProvider.parseRefreshTokenSessionId(refreshToken);
		assertThat(refreshSessionStore.find(sessionId))
				.contains(new RefreshSession(userId, TokenHasher.sha256Hex(refreshToken)));
	}

	@Test
	void 비밀번호가_틀리면_401_INVALID_CREDENTIALS다() throws Exception {
		signup();

		mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(loginBody(LOGIN_ID, "wrong-password")))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"));
	}

	@Test
	void 존재하지_않는_아이디면_401_INVALID_CREDENTIALS다() throws Exception {
		mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(loginBody("nobody999", PASSWORD)))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"));
	}

	@Test
	void 탈퇴한_회원이_로그인하면_403_USER_DELETED다() throws Exception {
		signup();
		User user = userRepository.findByLoginId(LOGIN_ID).orElseThrow();
		user.markDeleted();
		userRepository.saveAndFlush(user);

		mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(loginBody(LOGIN_ID, PASSWORD)))
				.andExpect(status().isForbidden())
				.andExpect(jsonPath("$.code").value("USER_DELETED"));
	}
}

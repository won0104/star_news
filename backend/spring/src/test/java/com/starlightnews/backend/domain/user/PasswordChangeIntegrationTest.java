package com.starlightnews.backend.domain.user;

import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.jayway.jsonpath.JsonPath;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.security.JwtProvider;
import com.starlightnews.backend.global.security.RefreshSessionStore;
import com.starlightnews.backend.global.security.TokenBlacklist;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasItems;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.cookie;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class PasswordChangeIntegrationTest {

	private static final String PATH = ApiPaths.API_V1 + "/users/me/password";
	private static final String LOGIN_PATH = ApiPaths.API_V1 + "/auth/login";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ObjectMapper objectMapper;

	@Autowired
	private UserRepository userRepository;

	@Autowired
	private PasswordEncoder passwordEncoder;

	@Autowired
	private JwtProvider jwtProvider;

	@Autowired
	private RefreshSessionStore refreshSessionStore;

	@Autowired
	private TokenBlacklist tokenBlacklist;

	@Autowired
	private EntityManager entityManager;

	private record Tokens(String accessToken, String refreshToken) {
	}

	private long saveUser(String loginId) {
		return userRepository.saveAndFlush(
				User.create(loginId, passwordEncoder.encode("password1234"), "별빛")).getId();
	}

	private Tokens login(String loginId, String password) throws Exception {
		MvcResult result = mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(loginBody(loginId, password)))
				.andExpect(status().isOk())
				.andReturn();
		return new Tokens(
				JsonPath.read(result.getResponse().getContentAsString(), "$.data.accessToken"),
				result.getResponse().getCookie("refreshToken").getValue());
	}

	private String body(String currentPassword, String newPassword) throws Exception {
		return objectMapper.writeValueAsString(Map.of(
				"currentPassword", currentPassword, "newPassword", newPassword));
	}

	@Test
	void 비밀번호_변경_후_모든_Refresh_세션과_현재_Access_Token을_무효화한다() throws Exception {
		long userId = saveUser("password_user_a");
		Tokens first = login("password_user_a", "password1234");
		Tokens second = login("password_user_a", "password1234");
		String firstSessionId = jwtProvider.parseRefreshTokenSessionId(first.refreshToken());
		String secondSessionId = jwtProvider.parseRefreshTokenSessionId(second.refreshToken());
		String firstJti = jwtProvider.parseAccessToken(first.accessToken()).jti();
		entityManager.clear();

		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + first.accessToken())
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("password1234", "newPassword1234")))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data").doesNotExist())
				.andExpect(jsonPath("$.meta.requestId").isString())
				.andExpect(cookie().value("refreshToken", ""))
				.andExpect(cookie().maxAge("refreshToken", 0))
				.andExpect(cookie().path("refreshToken", "/api/v1/auth"));

		entityManager.flush();
		entityManager.clear();
		assertThat(passwordEncoder.matches("newPassword1234",
				userRepository.findById(userId).orElseThrow().getPasswordHash())).isTrue();
		assertThat(refreshSessionStore.find(firstSessionId)).isEmpty();
		assertThat(refreshSessionStore.find(secondSessionId)).isEmpty();
		assertThat(tokenBlacklist.isBlacklisted(firstJti)).isTrue();

		mockMvc.perform(get(ApiPaths.API_V1 + "/users/me")
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + first.accessToken()))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_ACCESS_TOKEN"));
		mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(loginBody("password_user_a", "password1234")))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"));
		login("password_user_a", "newPassword1234");
	}

	private String loginBody(String loginId, String password) throws Exception {
		return objectMapper.writeValueAsString(Map.of("loginId", loginId, "password", password));
	}

	@Test
	void 현재_비밀번호가_틀리면_401이고_비밀번호와_세션을_유지한다() throws Exception {
		long userId = saveUser("password_user_b");
		Tokens tokens = login("password_user_b", "password1234");
		String sessionId = jwtProvider.parseRefreshTokenSessionId(tokens.refreshToken());

		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken())
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("wrongPassword", "newPassword1234")))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"));

		assertThat(passwordEncoder.matches("password1234",
				userRepository.findById(userId).orElseThrow().getPasswordHash())).isTrue();
		assertThat(refreshSessionStore.find(sessionId)).isPresent();
	}

	@Test
	void 새_비밀번호가_현재와_같으면_400이고_세션을_유지한다() throws Exception {
		saveUser("password_user_c");
		Tokens tokens = login("password_user_c", "password1234");
		String sessionId = jwtProvider.parseRefreshTokenSessionId(tokens.refreshToken());

		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken())
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("password1234", "password1234")))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));

		assertThat(refreshSessionStore.find(sessionId)).isPresent();
	}

	@Test
	void 새_비밀번호가_짧으면_400_필드_오류를_응답한다() throws Exception {
		saveUser("password_user_d");
		Tokens tokens = login("password_user_d", "password1234");

		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + tokens.accessToken())
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("password1234", "short")))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"))
				.andExpect(jsonPath("$.errors[*].field").value(hasItems("newPassword")));
	}

	@Test
	void 인증_토큰이_없으면_401을_응답한다() throws Exception {
		mockMvc.perform(patch(PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("password1234", "newPassword1234")))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"));
	}
}

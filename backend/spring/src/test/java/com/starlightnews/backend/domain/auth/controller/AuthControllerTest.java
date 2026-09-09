package com.starlightnews.backend.domain.auth.controller;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.jayway.jsonpath.JsonPath;
import com.starlightnews.backend.domain.auth.dto.LoginIdAvailabilityResponse;
import com.starlightnews.backend.domain.auth.dto.LoginResponse;
import com.starlightnews.backend.domain.auth.dto.LoginResult;
import com.starlightnews.backend.domain.auth.dto.SignupResponse;
import com.starlightnews.backend.domain.auth.exception.AuthErrorCode;
import com.starlightnews.backend.domain.auth.service.AuthService;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasItems;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.cookie;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(AuthController.class)
@Import({SecurityConfig.class, JwtProvider.class})
@ActiveProfiles("test")
class AuthControllerTest {

	private static final String SIGNUP_PATH = ApiPaths.API_V1 + "/auth/signup";
	private static final String AVAILABILITY_PATH = ApiPaths.API_V1 + "/auth/login-id/availability";
	private static final String LOGIN_PATH = ApiPaths.API_V1 + "/auth/login";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ObjectMapper objectMapper;

	@MockitoBean
	private AuthService authService;

	private String body(Object loginId, Object password, Object nickname,
			List<String> interested, List<String> disliked) throws Exception {
		return objectMapper.writeValueAsString(Map.of(
				"loginId", loginId,
				"password", password,
				"nickname", nickname,
				"interestedTopicCodes", interested,
				"dislikedTopicCodes", disliked
		));
	}

	@Test
	void 회원가입_성공시_201과_data_meta_구조로_응답한다() throws Exception {
		given(authService.signup(any())).willReturn(new SignupResponse(
				1L, "starlight01", "별빛", List.of(TopicCode.ECONOMY, TopicCode.IT_SCIENCE), List.of(TopicCode.SPORTS)));

		mockMvc.perform(post(SIGNUP_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("starlight01", "password1234", "별빛",
								List.of("ECONOMY", "IT_SCIENCE"), List.of("SPORTS"))))
				.andExpect(status().isCreated())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.userId").value(1))
				.andExpect(jsonPath("$.data.loginId").value("starlight01"))
				.andExpect(jsonPath("$.data.nickname").value("별빛"))
				.andExpect(jsonPath("$.data.interestedTopicCodes").value(hasItems("ECONOMY", "IT_SCIENCE")))
				.andExpect(jsonPath("$.data.dislikedTopicCodes[0]").value("SPORTS"))
				.andExpect(jsonPath("$.meta.requestId").isString())
				.andExpect(result -> assertThat(
						JsonPath.<String>read(result.getResponse().getContentAsString(), "$.meta.requestId"))
						.isEqualTo(result.getResponse().getHeader(RequestIdFilter.HEADER_NAME)));
	}

	@Test
	void 요청_본문이_형식_규칙을_위반하면_400_INVALID_INPUT_VALUE와_필드별_errors를_응답한다() throws Exception {
		mockMvc.perform(post(SIGNUP_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("ab", "short", "", List.of(), List.of())))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"))
				.andExpect(jsonPath("$.errors").isArray())
				.andExpect(jsonPath("$.errors[*].field").value(hasItems("loginId", "password", "nickname")));

		verify(authService, never()).signup(any());
	}

	@Test
	void 서비스가_LOGIN_ID_ALREADY_EXISTS를_던지면_409로_응답한다() throws Exception {
		given(authService.signup(any()))
				.willThrow(new BusinessException(AuthErrorCode.LOGIN_ID_ALREADY_EXISTS));

		mockMvc.perform(post(SIGNUP_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("starlight01", "password1234", "별빛", List.of(), List.of())))
				.andExpect(status().isConflict())
				.andExpect(jsonPath("$.code").value("LOGIN_ID_ALREADY_EXISTS"))
				.andExpect(jsonPath("$.requestId").isString());
	}

	@Test
	void 서비스가_INVALID_TOPIC을_던지면_400_INVALID_TOPIC으로_응답한다() throws Exception {
		given(authService.signup(any()))
				.willThrow(new BusinessException(AuthErrorCode.INVALID_TOPIC));

		mockMvc.perform(post(SIGNUP_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("starlight01", "password1234", "별빛", List.of("MOVIE"), List.of())))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_TOPIC"));
	}

	@Test
	void 아이디_사용_가능하면_200과_available_true를_응답한다() throws Exception {
		given(authService.checkLoginIdAvailability("newbie123"))
				.willReturn(new LoginIdAvailabilityResponse("newbie123", true));

		mockMvc.perform(get(AVAILABILITY_PATH).param("loginId", "newbie123"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.loginId").value("newbie123"))
				.andExpect(jsonPath("$.data.available").value(true))
				.andExpect(jsonPath("$.meta.requestId").isString());
	}

	@Test
	void 아이디가_이미_사용중이면_200과_available_false를_응답한다() throws Exception {
		given(authService.checkLoginIdAvailability("starlight01"))
				.willReturn(new LoginIdAvailabilityResponse("starlight01", false));

		mockMvc.perform(get(AVAILABILITY_PATH).param("loginId", "starlight01"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.available").value(false));
	}

	@Test
	void 형식이_틀린_아이디로_조회하면_400_INVALID_INPUT_VALUE를_응답한다() throws Exception {
		mockMvc.perform(get(AVAILABILITY_PATH).param("loginId", "ab"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));

		verify(authService, never()).checkLoginIdAvailability(any());
	}

	private String loginBody(String loginId, String password) throws Exception {
		return objectMapper.writeValueAsString(Map.of("loginId", loginId, "password", password));
	}

	@Test
	void 로그인_성공시_200과_body_그리고_refreshToken_쿠키를_응답한다() throws Exception {
		LoginResponse body = new LoginResponse(
				"access-token-value", "Bearer", 3600L,
				new LoginResponse.UserSummary(1L, "starlight01", "별빛"));
		given(authService.login(any()))
				.willReturn(new LoginResult(body, "refresh-token-value", 1_209_600L));

		mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(loginBody("starlight01", "password1234")))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.accessToken").value("access-token-value"))
				.andExpect(jsonPath("$.data.tokenType").value("Bearer"))
				.andExpect(jsonPath("$.data.expiresIn").value(3600))
				.andExpect(jsonPath("$.data.user.userId").value(1))
				.andExpect(jsonPath("$.data.user.loginId").value("starlight01"))
				.andExpect(jsonPath("$.data.user.nickname").value("별빛"))
				.andExpect(jsonPath("$.meta.requestId").isString())
				.andExpect(cookie().value("refreshToken", "refresh-token-value"))
				.andExpect(cookie().httpOnly("refreshToken", true))
				.andExpect(cookie().secure("refreshToken", true))
				.andExpect(cookie().sameSite("refreshToken", "Lax"))
				.andExpect(cookie().path("refreshToken", "/api/v1/auth"))
				.andExpect(cookie().maxAge("refreshToken", 1_209_600));
	}

	@Test
	void 로그인_요청_본문이_비어있으면_400_INVALID_INPUT_VALUE를_응답한다() throws Exception {
		mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(loginBody("", "")))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"))
				.andExpect(jsonPath("$.errors[*].field").value(hasItems("loginId", "password")));

		verify(authService, never()).login(any());
	}

	@Test
	void 서비스가_INVALID_CREDENTIALS를_던지면_401을_응답한다() throws Exception {
		given(authService.login(any()))
				.willThrow(new BusinessException(AuthErrorCode.INVALID_CREDENTIALS));

		mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(loginBody("starlight01", "wrong-password")))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"));
	}

	@Test
	void 서비스가_USER_DELETED를_던지면_403을_응답한다() throws Exception {
		given(authService.login(any()))
				.willThrow(new BusinessException(AuthErrorCode.USER_DELETED));

		mockMvc.perform(post(LOGIN_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(loginBody("starlight01", "password1234")))
				.andExpect(status().isForbidden())
				.andExpect(jsonPath("$.code").value("USER_DELETED"));
	}
}

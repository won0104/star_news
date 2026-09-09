package com.starlightnews.backend.domain.user.controller;

import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.domain.auth.exception.AuthErrorCode;
import com.starlightnews.backend.domain.user.service.UserService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.security.InMemoryTokenBlacklist;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasItems;
import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.cookie;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(UserController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class UserControllerTest {

	private static final String WITHDRAWAL_PATH = "/api/v1/users/me";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ObjectMapper objectMapper;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private UserService userService;

	private String bearer(long userId) {
		return "Bearer " + jwtProvider.createAccessToken(userId);
	}

	private String body(String password) throws Exception {
		return password == null
				? objectMapper.writeValueAsString(Map.of())
				: objectMapper.writeValueAsString(Map.of("password", password));
	}

	@Test
	void 탈퇴_성공시_200과_null_data_그리고_만료된_refreshToken_쿠키를_응답한다() throws Exception {
		mockMvc.perform(delete(WITHDRAWAL_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("password1234")))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data").value(nullValue()))
				.andExpect(jsonPath("$.meta.requestId").isString())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(cookie().value("refreshToken", ""))
				.andExpect(cookie().maxAge("refreshToken", 0))
				.andExpect(cookie().path("refreshToken", "/api/v1/auth"));

		verify(userService).withdraw(eq(1L), anyString(), any(), eq("password1234"));
	}

	@Test
	void 비밀번호_누락시_400_INVALID_INPUT_VALUE와_필드_errors를_응답한다() throws Exception {
		mockMvc.perform(delete(WITHDRAWAL_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.contentType(MediaType.APPLICATION_JSON)
						.content(body(null)))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"))
				.andExpect(jsonPath("$.errors[*].field").value(hasItems("password")));

		verify(userService, never()).withdraw(anyLong(), anyString(), any(), anyString());
	}

	@Test
	void 서비스가_INVALID_CREDENTIALS를_던지면_401을_응답한다() throws Exception {
		willThrow(new BusinessException(AuthErrorCode.INVALID_CREDENTIALS))
				.given(userService).withdraw(anyLong(), anyString(), any(), anyString());

		mockMvc.perform(delete(WITHDRAWAL_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("wrong-password")))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_CREDENTIALS"));
	}

	@Test
	void 서비스가_USER_DELETED를_던지면_403을_응답한다() throws Exception {
		willThrow(new BusinessException(AuthErrorCode.USER_DELETED))
				.given(userService).withdraw(anyLong(), anyString(), any(), anyString());

		mockMvc.perform(delete(WITHDRAWAL_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("password1234")))
				.andExpect(status().isForbidden())
				.andExpect(jsonPath("$.code").value("USER_DELETED"));
	}

	@Test
	void 인증_토큰이_없으면_401_UNAUTHORIZED를_응답한다() throws Exception {
		mockMvc.perform(delete(WITHDRAWAL_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("password1234")))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"));

		verify(userService, never()).withdraw(anyLong(), anyString(), any(), anyString());
	}
}

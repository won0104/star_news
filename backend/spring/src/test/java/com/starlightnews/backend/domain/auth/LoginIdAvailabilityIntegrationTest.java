package com.starlightnews.backend.domain.auth;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.global.constant.ApiPaths;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class LoginIdAvailabilityIntegrationTest {

	private static final String SIGNUP_PATH = ApiPaths.API_V1 + "/auth/signup";
	private static final String AVAILABILITY_PATH = ApiPaths.API_V1 + "/auth/login-id/availability";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ObjectMapper objectMapper;

	private void signup(String loginId) throws Exception {
		String body = objectMapper.writeValueAsString(Map.of(
				"loginId", loginId,
				"password", "password1234",
				"nickname", "별빛",
				"interestedTopicCodes", List.of(),
				"dislikedTopicCodes", List.of()
		));
		mockMvc.perform(post(SIGNUP_PATH).contentType(MediaType.APPLICATION_JSON).content(body))
				.andExpect(status().isCreated());
	}

	@Test
	void 가입되지_않은_아이디는_available_true다() throws Exception {
		mockMvc.perform(get(AVAILABILITY_PATH).param("loginId", "brandnew01"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.loginId").value("brandnew01"))
				.andExpect(jsonPath("$.data.available").value(true))
				.andExpect(jsonPath("$.meta.requestId").isString());
	}

	@Test
	void 가입된_아이디는_available_false다() throws Exception {
		signup("starlight01");

		mockMvc.perform(get(AVAILABILITY_PATH).param("loginId", "starlight01"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.available").value(false));
	}

	@Test
	void 형식이_틀린_아이디는_400_INVALID_INPUT_VALUE다() throws Exception {
		mockMvc.perform(get(AVAILABILITY_PATH).param("loginId", "AB"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"))
				.andExpect(jsonPath("$.errors").isArray());
	}
}

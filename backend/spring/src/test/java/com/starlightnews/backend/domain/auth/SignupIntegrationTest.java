package com.starlightnews.backend.domain.auth;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.domain.UserInterest;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.TopicCode;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;
import static org.hamcrest.Matchers.hasItems;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class SignupIntegrationTest {

	private static final String SIGNUP_PATH = ApiPaths.API_V1 + "/auth/signup";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ObjectMapper objectMapper;

	@Autowired
	private UserRepository userRepository;

	@Autowired
	private PasswordEncoder passwordEncoder;

	private String body(String loginId, String password, String nickname,
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
	void 회원가입_전체_흐름_사용자와_관심분야가_DB에_저장된다() throws Exception {
		mockMvc.perform(post(SIGNUP_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("starlight01", "password1234", "별빛",
								List.of("ECONOMY", "IT_SCIENCE"), List.of("SPORTS"))))
				.andExpect(status().isCreated())
				.andExpect(jsonPath("$.data.userId").isNumber())
				.andExpect(jsonPath("$.data.loginId").value("starlight01"))
				.andExpect(jsonPath("$.data.nickname").value("별빛"))
				.andExpect(jsonPath("$.data.interestedTopicCodes").value(hasItems("ECONOMY", "IT_SCIENCE")))
				.andExpect(jsonPath("$.data.dislikedTopicCodes[0]").value("SPORTS"))
				.andExpect(jsonPath("$.meta.requestId").isString());

		User user = userRepository.findByLoginId("starlight01").orElseThrow();
		assertThat(user.getId()).isNotNull();
		assertThat(user.getNickname()).isEqualTo("별빛");
		assertThat(user.getPasswordHash()).isNotEqualTo("password1234");
		assertThat(passwordEncoder.matches("password1234", user.getPasswordHash())).isTrue();
		assertThat(user.getInterests())
				.extracting(interest -> interest.getId().getTopicCode(), UserInterest::getInterestType)
				.containsExactlyInAnyOrder(
						tuple(TopicCode.ECONOMY, InterestType.INTEREST),
						tuple(TopicCode.IT_SCIENCE, InterestType.INTEREST),
						tuple(TopicCode.SPORTS, InterestType.DISLIKE)
				);
	}

	@Test
	void 관심분야_없이_회원가입하면_사용자만_저장된다() throws Exception {
		mockMvc.perform(post(SIGNUP_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("starlight01", "password1234", "별빛", List.of(), List.of())))
				.andExpect(status().isCreated())
				.andExpect(jsonPath("$.data.interestedTopicCodes").isEmpty())
				.andExpect(jsonPath("$.data.dislikedTopicCodes").isEmpty());

		User user = userRepository.findByLoginId("starlight01").orElseThrow();
		assertThat(user.getInterests()).isEmpty();
	}

	@Test
	void 같은_로그인_아이디로_다시_가입하면_409이고_중복_저장되지_않는다() throws Exception {
		mockMvc.perform(post(SIGNUP_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("starlight01", "password1234", "별빛", List.of(), List.of())))
				.andExpect(status().isCreated());

		mockMvc.perform(post(SIGNUP_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("starlight01", "another12345", "다른별빛", List.of(), List.of())))
				.andExpect(status().isConflict())
				.andExpect(jsonPath("$.code").value("LOGIN_ID_ALREADY_EXISTS"));

		assertThat(userRepository.count()).isEqualTo(1);
	}

	@Test
	void 존재하지_않는_토픽_코드로_가입하면_400이고_저장되지_않는다() throws Exception {
		mockMvc.perform(post(SIGNUP_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("starlight01", "password1234", "별빛", List.of("MOVIE"), List.of())))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_TOPIC"));

		assertThat(userRepository.count()).isZero();
	}

	@Test
	void 형식_위반_요청은_400_INVALID_INPUT_VALUE이고_저장되지_않는다() throws Exception {
		mockMvc.perform(post(SIGNUP_PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content(body("ab", "short", "", List.of(), List.of())))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"))
				.andExpect(jsonPath("$.errors[*].field").value(hasItems("loginId", "password", "nickname")));

		assertThat(userRepository.count()).isZero();
	}
}

package com.starlightnews.backend.domain.user;

import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.security.JwtProvider;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasItems;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class NicknameUpdateIntegrationTest {

	private static final String PATH = ApiPaths.API_V1 + "/users/me";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private UserRepository userRepository;

	@Autowired
	private JwtProvider jwtProvider;

	@Autowired
	private EntityManager entityManager;

	private String bearer(long userId) {
		return "Bearer " + jwtProvider.createAccessToken(userId);
	}

	@Test
	void 닉네임을_수정하고_사용자_정보와_토픽을_반환한다() throws Exception {
		User user = User.create("nickname_user", "hashed-password", "기존닉네임");
		user.addInterest(TopicCode.IT_SCIENCE, InterestType.INTEREST);
		user.addInterest(TopicCode.POLITICS, InterestType.INTEREST);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(userId))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"nickname\":\"새로운닉네임\"}"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.userId").value(userId))
				.andExpect(jsonPath("$.data.loginId").value("nickname_user"))
				.andExpect(jsonPath("$.data.nickname").value("새로운닉네임"))
				.andExpect(jsonPath("$.data.interestedTopicCodes[0]").value("POLITICS"))
				.andExpect(jsonPath("$.data.interestedTopicCodes[1]").value("IT_SCIENCE"))
				.andExpect(jsonPath("$.data.dislikedTopicCodes[0]").value("SPORTS"))
				.andExpect(jsonPath("$.meta.requestId").isString());

		entityManager.flush();
		entityManager.clear();
		User updated = userRepository.findById(userId).orElseThrow();
		assertThat(updated.getNickname()).isEqualTo("새로운닉네임");
		assertThat(updated.getLoginId()).isEqualTo("nickname_user");
	}

	@Test
	void 닉네임이_한_글자면_400이고_기존_값을_유지한다() throws Exception {
		User user = User.create("nickname_user", "hashed-password", "기존닉네임");
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(userId))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"nickname\":\"가\"}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"))
				.andExpect(jsonPath("$.errors[*].field").value(hasItems("nickname")));

		entityManager.clear();
		assertThat(userRepository.findById(userId).orElseThrow().getNickname()).isEqualTo("기존닉네임");
	}

	@Test
	void 인증_토큰이_없으면_401을_응답한다() throws Exception {
		mockMvc.perform(patch(PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"nickname\":\"새로운닉네임\"}"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"));
	}

	@Test
	void 탈퇴한_사용자는_404를_응답한다() throws Exception {
		User user = User.create("nickname_user", "hashed-password", "기존닉네임");
		user.markDeleted();
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(userId))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"nickname\":\"새로운닉네임\"}"))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("USER_NOT_FOUND"));
	}
}

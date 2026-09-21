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

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class UserProfileIntegrationTest {

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
	void 저장된_사용자_정보와_관심_비관심_Topic을_조회한다() throws Exception {
		User user = User.create("profile_user", "hashed-password", "기존닉네임");
		user.addInterest(TopicCode.IT_SCIENCE, InterestType.INTEREST);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		user.addInterest(TopicCode.POLITICS, InterestType.INTEREST);
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer(userId)))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.userId").value(userId))
				.andExpect(jsonPath("$.data.loginId").value("profile_user"))
				.andExpect(jsonPath("$.data.nickname").value("기존닉네임"))
				.andExpect(jsonPath("$.data.interestedTopicCodes[0]").value("POLITICS"))
				.andExpect(jsonPath("$.data.interestedTopicCodes[1]").value("IT_SCIENCE"))
				.andExpect(jsonPath("$.data.dislikedTopicCodes[0]").value("SPORTS"))
				.andExpect(jsonPath("$.data.passwordHash").doesNotExist())
				.andExpect(jsonPath("$.meta.requestId").isString());
	}

	@Test
	void 닉네임_수정_후_다시_조회하면_최신_정보와_빈_Topic_배열을_반환한다() throws Exception {
		User user = User.create("profile_user", "hashed-password", "기존닉네임");
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(userId))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"nickname\":\"새닉네임\"}"))
				.andExpect(status().isOk());
		entityManager.flush();
		entityManager.clear();

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer(userId)))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.nickname").value("새닉네임"))
				.andExpect(jsonPath("$.data.interestedTopicCodes").isEmpty())
				.andExpect(jsonPath("$.data.dislikedTopicCodes").isEmpty());
	}

	@Test
	void 인증_토큰이_없으면_401을_응답한다() throws Exception {
		mockMvc.perform(get(PATH))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"));
	}

	@Test
	void 탈퇴한_사용자는_404를_응답한다() throws Exception {
		User user = User.create("profile_user", "hashed-password", "기존닉네임");
		user.markDeleted();
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer(userId)))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("USER_NOT_FOUND"));
	}
}

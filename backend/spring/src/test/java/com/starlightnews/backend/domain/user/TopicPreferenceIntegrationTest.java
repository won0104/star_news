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
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class TopicPreferenceIntegrationTest {

	private static final String INTERESTS_PATH = ApiPaths.API_V1 + "/users/me/topic-preferences/interests";

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
	void DB에_저장된_관심_Topic만_Enum_순서로_조회한다() throws Exception {
		User user = User.create("starlight01", "hashed-password", "별빛");
		user.addInterest(TopicCode.IT_SCIENCE, InterestType.INTEREST);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		user.addInterest(TopicCode.POLITICS, InterestType.INTEREST);
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(get(INTERESTS_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(userId)))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.topicCodes[0]").value("POLITICS"))
				.andExpect(jsonPath("$.data.topicCodes[1]").value("IT_SCIENCE"))
				.andExpect(jsonPath("$.data.topicCodes.length()").value(2))
				.andExpect(jsonPath("$.meta.requestId").isString());
	}

	@Test
	void DB에_관심_Topic이_없으면_빈_배열을_응답한다() throws Exception {
		User user = User.create("starlight01", "hashed-password", "별빛");
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(get(INTERESTS_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(userId)))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.topicCodes").isArray())
				.andExpect(jsonPath("$.data.topicCodes").isEmpty());
	}

	@Test
	void DB에_사용자가_없으면_404_USER_NOT_FOUND를_응답한다() throws Exception {
		mockMvc.perform(get(INTERESTS_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(Long.MAX_VALUE)))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("USER_NOT_FOUND"));
	}
}

package com.starlightnews.backend.domain.user;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
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
	private ObjectMapper objectMapper;

	@Autowired
	private UserRepository userRepository;

	@Autowired
	private JwtProvider jwtProvider;

	@Autowired
	private EntityManager entityManager;

	private String bearer(long userId) {
		return "Bearer " + jwtProvider.createAccessToken(userId);
	}

	private String body(List<String> topicCodes) throws Exception {
		return objectMapper.writeValueAsString(Map.of("topicCodes", topicCodes));
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

	@Test
	void 관심_Topic_변경사항이_DB에_최종_상태로_저장된다() throws Exception {
		User user = User.create("starlight01", "hashed-password", "별빛");
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		user.addInterest(TopicCode.IT_SCIENCE, InterestType.INTEREST);
		user.addInterest(TopicCode.POLITICS, InterestType.DISLIKE);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(put(INTERESTS_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(userId))
						.contentType(MediaType.APPLICATION_JSON)
						.content(body(List.of("POLITICS", "CULTURE", "IT_SCIENCE"))))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.topicCodes[0]").value("POLITICS"))
				.andExpect(jsonPath("$.data.topicCodes[1]").value("CULTURE"))
				.andExpect(jsonPath("$.data.topicCodes[2]").value("IT_SCIENCE"));

		entityManager.flush();
		entityManager.clear();
		User updated = userRepository.findById(userId).orElseThrow();
		assertThat(updated.getTopicCodes(InterestType.INTEREST))
				.containsExactly(TopicCode.POLITICS, TopicCode.CULTURE, TopicCode.IT_SCIENCE);
		assertThat(updated.getTopicCodes(InterestType.DISLIKE))
				.containsExactly(TopicCode.SPORTS);
	}

	@Test
	void 빈_배열로_변경하면_DB의_관심_Topic만_모두_삭제된다() throws Exception {
		User user = User.create("starlight01", "hashed-password", "별빛");
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(put(INTERESTS_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(userId))
						.contentType(MediaType.APPLICATION_JSON)
						.content(body(List.of())))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.topicCodes").isEmpty());

		entityManager.flush();
		entityManager.clear();
		User updated = userRepository.findById(userId).orElseThrow();
		assertThat(updated.getTopicCodes(InterestType.INTEREST)).isEmpty();
		assertThat(updated.getTopicCodes(InterestType.DISLIKE))
				.containsExactly(TopicCode.SPORTS);
	}

	@Test
	void 잘못된_Topic으로_변경하면_400이고_DB_상태는_유지된다() throws Exception {
		User user = User.create("starlight01", "hashed-password", "별빛");
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		long userId = userRepository.saveAndFlush(user).getId();
		entityManager.clear();

		mockMvc.perform(put(INTERESTS_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(userId))
						.contentType(MediaType.APPLICATION_JSON)
						.content(body(List.of("MOVIE"))))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_TOPIC"));

		entityManager.clear();
		User unchanged = userRepository.findById(userId).orElseThrow();
		assertThat(unchanged.getTopicCodes(InterestType.INTEREST))
				.containsExactly(TopicCode.ECONOMY);
	}
}

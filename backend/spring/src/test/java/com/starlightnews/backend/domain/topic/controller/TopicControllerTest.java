package com.starlightnews.backend.domain.topic.controller;

import com.starlightnews.backend.domain.topic.service.TopicService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.security.InMemoryTokenBlacklist;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(TopicController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class, TopicService.class})
@ActiveProfiles("test")
class TopicControllerTest {

	@Autowired
	private MockMvc mockMvc;

	@Test
	void 인증_없이_전체_Topic을_Enum_순서와_한글_표시명으로_조회한다() throws Exception {
		mockMvc.perform(get("/api/v1/topics"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.topics.length()").value(7))
				.andExpect(jsonPath("$.data.topics[0].code").value("POLITICS"))
				.andExpect(jsonPath("$.data.topics[0].labelKo").value("정치"))
				.andExpect(jsonPath("$.data.topics[6].code").value("IT_SCIENCE"))
				.andExpect(jsonPath("$.data.topics[6].labelKo").value("IT·과학"))
				.andExpect(jsonPath("$.meta.requestId").isString());
	}
}

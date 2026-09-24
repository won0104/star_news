package com.starlightnews.backend.domain.topic.controller;

import java.time.OffsetDateTime;
import java.util.List;

import com.starlightnews.backend.domain.topic.dto.TopicExplorationResponse;
import com.starlightnews.backend.domain.topic.exception.TopicExplorationErrorCode;
import com.starlightnews.backend.domain.topic.service.TopicExplorationService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.security.InMemoryTokenBlacklist;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(TopicExplorationController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class TopicExplorationControllerTest {

	private static final String PATH = "/api/v1/topics/ECONOMY/exploration";
	private static final String REQUEST_ID = "550e8400-e29b-41d4-a716-446655440000";

	@Autowired
	private MockMvc mockMvc;

	@MockitoBean
	private TopicExplorationService topicExplorationService;

	@Test
	void 비회원도_중심_Topic과_탐색_진입_Event를_조회한다() throws Exception {
		given(topicExplorationService.getTopicExploration("ECONOMY")).willReturn(sampleResponse());

		mockMvc.perform(get(PATH).header(RequestIdFilter.HEADER_NAME, REQUEST_ID))
				.andExpect(status().isOk())
				.andExpect(header().string(RequestIdFilter.HEADER_NAME, REQUEST_ID))
				.andExpect(jsonPath("$.meta.requestId").value(REQUEST_ID))
				.andExpect(jsonPath("$.data.snapshotAt").value("2026-09-24T18:00:00+09:00"))
				.andExpect(jsonPath("$.data.centerTopic.nodeType").value("TOPIC"))
				.andExpect(jsonPath("$.data.centerTopic.topicCode").value("ECONOMY"))
				.andExpect(jsonPath("$.data.centerTopic.label").value("경제"))
				.andExpect(jsonPath("$.data.entryNodes.length()").value(1))
				.andExpect(jsonPath("$.data.entryNodes[0].entryNodeId").value(201))
				.andExpect(jsonPath("$.data.entryNodes[0].rank").value(1))
				.andExpect(jsonPath("$.data.entryNodes[0].nodeType").value("EVENT"))
				.andExpect(jsonPath("$.data.entryNodes[0].nodeKey").value("economy-event-1"))
				.andExpect(jsonPath("$.data.entryNodes[0].label").value("한국은행 기준금리 동결"))
				.andExpect(jsonPath("$.data.entryNodes[0].articleCount").value(23));

		verify(topicExplorationService).getTopicExploration("ECONOMY");
	}

	@Test
	void 결과가_없어도_200과_null_시각_및_빈_목록을_응답한다() throws Exception {
		given(topicExplorationService.getTopicExploration("ECONOMY")).willReturn(
				new TopicExplorationResponse(
						null,
						new TopicExplorationResponse.CenterTopic(NodeType.TOPIC, TopicCode.ECONOMY, "경제"),
						List.of()));

		mockMvc.perform(get(PATH))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.snapshotAt").hasJsonPath())
				.andExpect(jsonPath("$.data.snapshotAt").value(nullValue()))
				.andExpect(jsonPath("$.data.entryNodes").isEmpty());
	}

	@Test
	void 잘못된_Topic은_400_INVALID_TOPIC_CODE를_응답한다() throws Exception {
		String invalidPath = "/api/v1/topics/UNKNOWN/exploration";
		given(topicExplorationService.getTopicExploration("UNKNOWN"))
				.willThrow(new BusinessException(TopicExplorationErrorCode.INVALID_TOPIC_CODE));

		mockMvc.perform(get(invalidPath))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_TOPIC_CODE"))
				.andExpect(jsonPath("$.path").value(invalidPath));
	}

	@Test
	void 조회_실패는_500_TOPIC_EXPLORATION_FETCH_FAILED를_응답한다() throws Exception {
		given(topicExplorationService.getTopicExploration("ECONOMY"))
				.willThrow(new BusinessException(TopicExplorationErrorCode.TOPIC_EXPLORATION_FETCH_FAILED));

		mockMvc.perform(get(PATH))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.code").value("TOPIC_EXPLORATION_FETCH_FAILED"))
				.andExpect(jsonPath("$.path").value(PATH));
	}

	private TopicExplorationResponse sampleResponse() {
		return new TopicExplorationResponse(
				OffsetDateTime.parse("2026-09-24T18:00:00+09:00"),
				new TopicExplorationResponse.CenterTopic(NodeType.TOPIC, TopicCode.ECONOMY, "경제"),
				List.of(new TopicExplorationResponse.EntryNode(
						201L,
						1,
						NodeType.EVENT,
						"economy-event-1",
						"한국은행 기준금리 동결",
						23)));
	}
}

package com.starlightnews.backend.domain.user.controller;

import java.util.List;

import com.jayway.jsonpath.JsonPath;
import com.starlightnews.backend.domain.user.dto.TopicPreferenceResponse;
import com.starlightnews.backend.domain.user.exception.UserErrorCode;
import com.starlightnews.backend.domain.user.service.TopicPreferenceService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.security.InMemoryTokenBlacklist;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(TopicPreferenceController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class TopicPreferenceControllerTest {

	private static final String INTERESTS_PATH = "/api/v1/users/me/topic-preferences/interests";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private TopicPreferenceService topicPreferenceService;

	private String bearer(long userId) {
		return "Bearer " + jwtProvider.createAccessToken(userId);
	}

	@Test
	void 관심_Topic_조회_성공시_200과_data_meta_구조로_응답한다() throws Exception {
		given(topicPreferenceService.getInterests(1L))
				.willReturn(new TopicPreferenceResponse(List.of(TopicCode.POLITICS, TopicCode.IT_SCIENCE)));

		mockMvc.perform(get(INTERESTS_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L)))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.topicCodes[0]").value("POLITICS"))
				.andExpect(jsonPath("$.data.topicCodes[1]").value("IT_SCIENCE"))
				.andExpect(jsonPath("$.data.topicCodes.length()").value(2))
				.andExpect(jsonPath("$.meta.requestId").isString())
				.andExpect(result -> assertThat(
						JsonPath.<String>read(result.getResponse().getContentAsString(), "$.meta.requestId"))
						.isEqualTo(result.getResponse().getHeader(RequestIdFilter.HEADER_NAME)));

		verify(topicPreferenceService).getInterests(1L);
	}

	@Test
	void 관심_Topic이_없으면_topicCodes는_빈_배열이다() throws Exception {
		given(topicPreferenceService.getInterests(1L))
				.willReturn(new TopicPreferenceResponse(List.of()));

		mockMvc.perform(get(INTERESTS_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L)))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.topicCodes").isArray())
				.andExpect(jsonPath("$.data.topicCodes").isEmpty());
	}

	@Test
	void 서비스가_USER_NOT_FOUND를_던지면_404를_응답한다() throws Exception {
		given(topicPreferenceService.getInterests(1L))
				.willThrow(new BusinessException(UserErrorCode.USER_NOT_FOUND));

		mockMvc.perform(get(INTERESTS_PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L)))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("USER_NOT_FOUND"))
				.andExpect(jsonPath("$.requestId").isString());
	}

	@Test
	void 인증_토큰이_없으면_401_UNAUTHORIZED를_응답한다() throws Exception {
		mockMvc.perform(get(INTERESTS_PATH))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"));

		verify(topicPreferenceService, never()).getInterests(anyLong());
	}
}

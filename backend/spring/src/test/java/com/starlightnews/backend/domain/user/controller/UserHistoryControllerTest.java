package com.starlightnews.backend.domain.user.controller;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.user.dto.ArticleHistoryResponse;
import com.starlightnews.backend.domain.user.exception.PersonalGraphErrorCode;
import com.starlightnews.backend.domain.user.service.ArticleHistoryService;
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
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(UserHistoryController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class UserHistoryControllerTest {

	private static final String HISTORY_PATH = "/api/v1/users/me/history";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private ArticleHistoryService articleHistoryService;

	private String bearer() {
		return "Bearer " + jwtProvider.createAccessToken(1L);
	}

	private ArticleHistoryResponse sampleHistory() {
		return new ArticleHistoryResponse(
				List.of(new ArticleHistoryResponse.Item(930001L, "한국은행, 기준금리 동결", "연합뉴스", "ECONOMY", "경제",
						OffsetDateTime.of(2026, 8, 31, 9, 10, 0, 0, ZoneOffset.ofHours(9)), 3,
						"한국은행은 기준금리를 현재 수준으로 유지하기로 했다.", true)),
				true, "opaque-cursor");
	}

	@Test
	void 열람기록_조회_성공시_200과_items_구조로_응답한다() throws Exception {
		given(articleHistoryService.getHistory(1L, null, 20, null)).willReturn(sampleHistory());

		mockMvc.perform(get(HISTORY_PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.items[0].articleId").value(930001))
				.andExpect(jsonPath("$.data.items[0].organizationName").value("연합뉴스"))
				.andExpect(jsonPath("$.data.items[0].topicName").value("경제"))
				.andExpect(jsonPath("$.data.items[0].clickCount").value(3))
				.andExpect(jsonPath("$.data.items[0].lastReadAt").value("2026-08-31T09:10:00+09:00"))
				.andExpect(jsonPath("$.data.items[0].bookmarked").value(true))
				.andExpect(jsonPath("$.data.hasNext").value(true))
				.andExpect(jsonPath("$.data.nextCursor").value("opaque-cursor"))
				.andExpect(jsonPath("$.meta.requestId").isString());

		verify(articleHistoryService).getHistory(eq(1L), isNull(), eq(20), isNull());
	}

	@Test
	void topicCode_size_cursor_쿼리파라미터를_서비스에_전달한다() throws Exception {
		given(articleHistoryService.getHistory(any(), any(), anyInt(), any())).willReturn(sampleHistory());

		mockMvc.perform(get(HISTORY_PATH)
						.param("topicCode", "ECONOMY").param("size", "5").param("cursor", "opaque-cursor")
						.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk());

		verify(articleHistoryService).getHistory(eq(1L), eq("ECONOMY"), eq(5), eq("opaque-cursor"));
	}

	@Test
	void size가_1미만이면_400_INVALID_INPUT_VALUE를_응답한다() throws Exception {
		mockMvc.perform(get(HISTORY_PATH).param("size", "0").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));

		verify(articleHistoryService, never()).getHistory(any(), any(), anyInt(), any());
	}

	@Test
	void size가_50초과면_400_INVALID_INPUT_VALUE를_응답한다() throws Exception {
		mockMvc.perform(get(HISTORY_PATH).param("size", "51").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));
	}

	@Test
	void 서비스가_INVALID_TOPIC_CODE를_던지면_400을_응답한다() throws Exception {
		given(articleHistoryService.getHistory(any(), any(), anyInt(), any()))
				.willThrow(new BusinessException(PersonalGraphErrorCode.INVALID_TOPIC_CODE));

		mockMvc.perform(get(HISTORY_PATH).param("topicCode", "NOPE").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_TOPIC_CODE"));
	}

	@Test
	void 서비스가_INVALID_CURSOR를_던지면_400을_응답한다() throws Exception {
		given(articleHistoryService.getHistory(any(), any(), anyInt(), any()))
				.willThrow(new BusinessException(GraphErrorCode.INVALID_CURSOR));

		mockMvc.perform(get(HISTORY_PATH).param("cursor", "broken").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_CURSOR"));
	}

	@Test
	void 토큰이_없으면_401이고_서비스를_호출하지_않는다() throws Exception {
		mockMvc.perform(get(HISTORY_PATH))
				.andExpect(status().isUnauthorized());

		verify(articleHistoryService, never()).getHistory(anyLong(), any(), anyInt(), any());
	}
}

package com.starlightnews.backend.domain.user.controller;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.user.dto.NewsReportResponse;
import com.starlightnews.backend.domain.user.dto.NewsReportResponse.Familiarity;
import com.starlightnews.backend.domain.user.exception.NewsReportErrorCode;
import com.starlightnews.backend.domain.user.service.NewsReportService;
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

import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(NewsReportController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class NewsReportControllerTest {

	private static final String PATH = "/api/v1/users/me/statistics/news-report";
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private NewsReportService newsReportService;

	@Test
	void 뉴스_리포트_조회_성공시_200과_명세_구조를_응답한다() throws Exception {
		given(newsReportService.getNewsReport(1L)).willReturn(sampleResponse());

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.period.from").value("2026-06-02"))
				.andExpect(jsonPath("$.data.period.to").value("2026-09-02"))
				.andExpect(jsonPath("$.data.totalReadArticleCount").value(67))
				.andExpect(jsonPath("$.data.sourceReads[0].organizationName").value("연합뉴스"))
				.andExpect(jsonPath("$.data.sourceReads[0].ratio").value(26.9))
				.andExpect(jsonPath("$.data.weeklyTopicTrend[0].topics[0].topicName").value("경제"))
				.andExpect(jsonPath("$.data.topicLandscape[0].nodeType").value("ENTITY"))
				.andExpect(jsonPath("$.data.topicLandscape[0].topicCode").doesNotExist())
				.andExpect(jsonPath("$.data.topicLandscape[0].userReadArticleCount").value(2))
				.andExpect(jsonPath("$.data.topicLandscape[0].globalReadArticleCount").value(126))
				.andExpect(jsonPath("$.data.topicLandscape[0].x").value(63.2))
				.andExpect(jsonPath("$.data.topicLandscape[0].y").value(22.0))
				.andExpect(jsonPath("$.data.topicLandscape[0].strong").value(true))
				.andExpect(jsonPath("$.data.topicLandscape[0].readArticleCount").doesNotExist())
				.andExpect(jsonPath("$.data.topicLandscape[0].familiarity").value("NEW"))
				.andExpect(jsonPath("$.data.generatedAt").value("2026-09-02T21:00:00+09:00"))
				.andExpect(jsonPath("$.meta.requestId").isString());

		verify(newsReportService).getNewsReport(1L);
	}

	@Test
	void 토큰이_없으면_401이고_서비스를_호출하지_않는다() throws Exception {
		mockMvc.perform(get(PATH))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"));

		verify(newsReportService, never()).getNewsReport(anyLong());
	}

	@Test
	void 집계가_실패하면_500_NEWS_REPORT_AGGREGATION_FAILED를_응답한다() throws Exception {
		given(newsReportService.getNewsReport(1L))
				.willThrow(new BusinessException(NewsReportErrorCode.NEWS_REPORT_AGGREGATION_FAILED));

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.code").value("NEWS_REPORT_AGGREGATION_FAILED"));
	}

	private String bearer() {
		return "Bearer " + jwtProvider.createAccessToken(1L);
	}

	private NewsReportResponse sampleResponse() {
		return new NewsReportResponse(
				new NewsReportResponse.Period(LocalDate.of(2026, 6, 2), LocalDate.of(2026, 9, 2)),
				67L,
				List.of(new NewsReportResponse.SourceRead(1L, "연합뉴스", 18L, 26.9)),
				List.of(new NewsReportResponse.WeeklyTopicTrend(
						LocalDate.of(2026, 8, 17),
						List.of(new NewsReportResponse.WeeklyTopic("ECONOMY", "경제", 5L)))),
				List.of(new NewsReportResponse.TopicLandscapeNode(
						"ENTITY", "entity-uuid", "HBM", null, 2L, 126L, 63.2, 22.0, true,
						OffsetDateTime.of(2026, 8, 28, 14, 10, 0, 0, KST),
						OffsetDateTime.of(2026, 8, 31, 11, 20, 0, 0, KST), Familiarity.NEW)),
				OffsetDateTime.of(2026, 9, 2, 21, 0, 0, 0, KST));
	}
}

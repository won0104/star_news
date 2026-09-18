package com.starlightnews.backend.domain.article.controller;

import java.time.OffsetDateTime;

import com.starlightnews.backend.domain.article.dto.ArticleDetailResponse;
import com.starlightnews.backend.domain.article.dto.ArticleSummaryResponse;
import com.starlightnews.backend.domain.article.dto.ArticleSummaryStatus;
import com.starlightnews.backend.domain.article.exception.ArticleErrorCode;
import com.starlightnews.backend.domain.article.service.ArticleDetailService;
import com.starlightnews.backend.domain.article.service.ArticleSummaryService;
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
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ArticleController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class ArticleControllerTest {

	private static final String DETAIL_PATH = "/api/v1/articles/{articleId}";
	private static final String SUMMARY_PATH = "/api/v1/articles/{articleId}/summary";
	private static final String REQUEST_ID = "550e8400-e29b-41d4-a716-446655440000";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private ArticleDetailService articleDetailService;

	@MockitoBean
	private ArticleSummaryService articleSummaryService;

	@Test
	void 비회원도_기사_요약을_생성하고_200을_응답받는다() throws Exception {
		given(articleSummaryService.generate(101L)).willReturn(new ArticleSummaryResponse(
				101L, "생성된 기사 요약", ArticleSummaryStatus.COMPLETED));

		mockMvc.perform(post(SUMMARY_PATH, 101L).header(RequestIdFilter.HEADER_NAME, REQUEST_ID))
				.andExpect(status().isOk())
				.andExpect(header().string(RequestIdFilter.HEADER_NAME, REQUEST_ID))
				.andExpect(jsonPath("$.data.articleId").value(101))
				.andExpect(jsonPath("$.data.summary").value("생성된 기사 요약"))
				.andExpect(jsonPath("$.data.summaryStatus").value("COMPLETED"))
				.andExpect(jsonPath("$.meta.requestId").value(REQUEST_ID));
	}

	@Test
	void 이미_요약_생성중이면_202_PROCESSING을_응답한다() throws Exception {
		given(articleSummaryService.generate(101L)).willReturn(new ArticleSummaryResponse(
				101L, null, ArticleSummaryStatus.PROCESSING));

		mockMvc.perform(post(SUMMARY_PATH, 101L))
				.andExpect(status().isAccepted())
				.andExpect(jsonPath("$.data.summary").isEmpty())
				.andExpect(jsonPath("$.data.summaryStatus").value("PROCESSING"));
	}

	@Test
	void 요약_API의_articleId가_숫자가_아니면_400_TYPE_MISMATCH를_응답한다() throws Exception {
		mockMvc.perform(post(SUMMARY_PATH, "not-a-number"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("TYPE_MISMATCH"));

		verify(articleSummaryService, never()).generate(anyLong());
	}

	@Test
	void 기사_본문이_없으면_422_ARTICLE_CONTENT_UNAVAILABLE를_응답한다() throws Exception {
		given(articleSummaryService.generate(101L))
				.willThrow(new BusinessException(ArticleErrorCode.ARTICLE_CONTENT_UNAVAILABLE));

		mockMvc.perform(post(SUMMARY_PATH, 101L))
				.andExpect(status().isUnprocessableEntity())
				.andExpect(jsonPath("$.code").value("ARTICLE_CONTENT_UNAVAILABLE"));
	}

	@Test
	void GMS_호출이_실패하면_502_SUMMARY_GENERATION_FAILED를_응답한다() throws Exception {
		given(articleSummaryService.generate(101L))
				.willThrow(new BusinessException(ArticleErrorCode.SUMMARY_GENERATION_FAILED));

		mockMvc.perform(post(SUMMARY_PATH, 101L))
				.andExpect(status().isBadGateway())
				.andExpect(jsonPath("$.code").value("SUMMARY_GENERATION_FAILED"));
	}

	@Test
	void 요약_저장이_실패하면_500_SUMMARY_SAVE_FAILED를_응답한다() throws Exception {
		given(articleSummaryService.generate(101L))
				.willThrow(new BusinessException(ArticleErrorCode.SUMMARY_SAVE_FAILED));

		mockMvc.perform(post(SUMMARY_PATH, 101L))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.code").value("SUMMARY_SAVE_FAILED"));
	}

	@Test
	void 비회원도_기사_상세와_요청_ID를_조회한다() throws Exception {
		given(articleDetailService.getDetail(101L, null)).willReturn(completedDetail(false));

		mockMvc.perform(get(DETAIL_PATH, 101L).header(RequestIdFilter.HEADER_NAME, REQUEST_ID))
				.andExpect(status().isOk())
				.andExpect(header().string(RequestIdFilter.HEADER_NAME, REQUEST_ID))
				.andExpect(jsonPath("$.meta.requestId").value(REQUEST_ID))
				.andExpect(jsonPath("$.data.articleId").value(101))
				.andExpect(jsonPath("$.data.title").value("국방부, 한미 연합훈련 일정 발표"))
				.andExpect(jsonPath("$.data.organizationName").value("연합뉴스"))
				.andExpect(jsonPath("$.data.publishedAt").value("2026-08-31T10:00:00+09:00"))
				.andExpect(jsonPath("$.data.summary").value("저장된 요약"))
				.andExpect(jsonPath("$.data.summaryStatus").value("COMPLETED"))
				.andExpect(jsonPath("$.data.originalUrl").value("https://news.example.com/articles/101"))
				.andExpect(jsonPath("$.data.bookmarked").value(false));

		verify(articleDetailService).getDetail(101L, null);
	}

	@Test
	void 로그인_사용자의_ID를_북마크_조회에_전달한다() throws Exception {
		given(articleDetailService.getDetail(101L, 1L)).willReturn(completedDetail(true));

		mockMvc.perform(get(DETAIL_PATH, 101L)
						.header(HttpHeaders.AUTHORIZATION,
								"Bearer " + jwtProvider.createAccessToken(1L)))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.bookmarked").value(true));

		verify(articleDetailService).getDetail(101L, 1L);
	}

	@Test
	void 잘못된_토큰이_있어도_비회원으로_조회한다() throws Exception {
		given(articleDetailService.getDetail(101L, null)).willReturn(completedDetail(false));

		mockMvc.perform(get(DETAIL_PATH, 101L)
						.header(HttpHeaders.AUTHORIZATION, "Bearer garbage"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.bookmarked").value(false));

		verify(articleDetailService).getDetail(101L, null);
	}

	@Test
	void 다른_요청이_요약_생성중이면_null과_PROCESSING을_응답한다() throws Exception {
		given(articleDetailService.getDetail(101L, null)).willReturn(new ArticleDetailResponse(
				101L,
				"국방부, 한미 연합훈련 일정 발표",
				"연합뉴스",
				OffsetDateTime.parse("2026-08-31T10:00:00+09:00"),
				null,
				ArticleSummaryStatus.PROCESSING,
				"https://news.example.com/articles/101",
				false));

		mockMvc.perform(get(DETAIL_PATH, 101L))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.summary").isEmpty())
				.andExpect(jsonPath("$.data.summaryStatus").value("PROCESSING"));
	}

	@Test
	void articleId가_숫자가_아니면_400_TYPE_MISMATCH를_응답한다() throws Exception {
		mockMvc.perform(get(DETAIL_PATH, "not-a-number"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("TYPE_MISMATCH"));

		verify(articleDetailService, never()).getDetail(anyLong(), any());
	}

	@Test
	void 기사가_없으면_404_ARTICLE_NOT_FOUND를_응답한다() throws Exception {
		given(articleDetailService.getDetail(999L, null))
				.willThrow(new BusinessException(ArticleErrorCode.ARTICLE_NOT_FOUND));

		mockMvc.perform(get(DETAIL_PATH, 999L))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("ARTICLE_NOT_FOUND"))
				.andExpect(jsonPath("$.path").value("/api/v1/articles/999"));
	}

	@Test
	void 상세_조회가_실패하면_500_ARTICLE_DETAIL_QUERY_FAILED를_응답한다() throws Exception {
		given(articleDetailService.getDetail(101L, null))
				.willThrow(new BusinessException(ArticleErrorCode.ARTICLE_DETAIL_QUERY_FAILED));

		mockMvc.perform(get(DETAIL_PATH, 101L))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.code").value("ARTICLE_DETAIL_QUERY_FAILED"));
	}

	private ArticleDetailResponse completedDetail(boolean bookmarked) {
		return new ArticleDetailResponse(
				101L,
				"국방부, 한미 연합훈련 일정 발표",
				"연합뉴스",
				OffsetDateTime.parse("2026-08-31T10:00:00+09:00"),
				"저장된 요약",
				ArticleSummaryStatus.COMPLETED,
				"https://news.example.com/articles/101",
				bookmarked);
	}
}

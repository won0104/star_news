package com.starlightnews.backend.domain.recommendation.controller;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.recommendation.dto.RecommendationBoardResponse;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationDetailResponse;
import com.starlightnews.backend.domain.recommendation.service.RecommendationBoardService;
import com.starlightnews.backend.domain.recommendation.service.RecommendationDetailService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import com.starlightnews.backend.global.enums.RecommendationType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
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
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(RecommendationController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class RecommendationControllerTest {

	private static final String PATH = "/api/v1/recommendations";
	private static final long USER_ID = 1L;

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private RecommendationBoardService recommendationBoardService;

	@MockitoBean
	private RecommendationDetailService recommendationDetailService;

	private String bearer() {
		return "Bearer " + jwtProvider.createAccessToken(USER_ID);
	}

	private RecommendationBoardResponse board() {
		OffsetDateTime availableAt = OffsetDateTime.of(2026, 9, 16, 18, 0, 0, 0, ZoneOffset.ofHours(9));
		return new RecommendationBoardResponse(
				RecommendationCycle.PM, availableAt.minusMinutes(30), availableAt,
				List.of(new RecommendationBoardResponse.Item(10241L,
						"00000020-0920-4000-8000-000000000001", "한국은행 1월 기준금리 동결",
						TopicCode.ECONOMY, new BigDecimal("0.920000"), (short) 1,
						RecommendationType.NORMAL)));
	}

	@Test
	void 추천_보드를_조회한다() throws Exception {
		given(recommendationBoardService.getBoard(USER_ID)).willReturn(board());

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.cycle").value("PM"))
				.andExpect(jsonPath("$.data.availableAt").value("2026-09-16T18:00:00+09:00"))
				.andExpect(jsonPath("$.data.items[0].userRecommendationId").value(10241))
				.andExpect(jsonPath("$.data.items[0].label").value("한국은행 1월 기준금리 동결"))
				.andExpect(jsonPath("$.data.items[0].topicCode").value("ECONOMY"))
				.andExpect(jsonPath("$.data.items[0].rank").value(1))
				.andExpect(jsonPath("$.data.items[0].recommendationType").value("NORMAL"));
	}

	@Test
	void 응답에_추천_이유가_없다() throws Exception {
		// FastAPI 가 추천 이유를 더 이상 보내지 않는다. 늘 비어 있는 필드를 내려보내지 않는다.
		given(recommendationBoardService.getBoard(USER_ID)).willReturn(board());

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items[0].reason").doesNotExist());
	}

	@Test
	void 응답에_페이지네이션_필드가_없다() throws Exception {
		given(recommendationBoardService.getBoard(USER_ID)).willReturn(board());

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.hasNext").doesNotExist())
				.andExpect(jsonPath("$.data.nextCursor").doesNotExist());
	}

	@Test
	void 토큰이_없으면_401이다() throws Exception {
		mockMvc.perform(get(PATH)).andExpect(status().isUnauthorized());

		verify(recommendationBoardService, never()).getBoard(anyLong());
	}

	@Test
	void 로그인한_사용자의_추천만_조회한다() throws Exception {
		given(recommendationBoardService.getBoard(USER_ID)).willReturn(board());

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk());

		verify(recommendationBoardService).getBoard(USER_ID);
	}

	@Test
	void 공개된_회차가_없으면_빈_목록을_200으로_돌려준다() throws Exception {
		given(recommendationBoardService.getBoard(USER_ID))
				.willReturn(RecommendationBoardResponse.empty());

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items").isEmpty())
				.andExpect(jsonPath("$.data.cycle").doesNotExist());
	}

	@Test
	void 남는_쿼리_파라미터는_무시한다() throws Exception {
		// 프론트가 예전 명세대로 size 를 붙여 보내도 그대로 동작해야 한다.
		given(recommendationBoardService.getBoard(USER_ID)).willReturn(board());

		mockMvc.perform(get(PATH).param("size", "10").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk());
	}

	// --- 추천 Event 상세 ---

	private RecommendationDetailResponse detail() {
		return new RecommendationDetailResponse(10241L,
				"00000020-0920-4000-8000-000000000001", "한국은행 1월 기준금리 동결",
				TopicCode.ECONOMY, "금통위가 기준금리를 동결했다.",
				List.of(new RecommendationDetailResponse.Article(930001L, "한국은행 기준금리 동결",
						"연합뉴스", OffsetDateTime.of(2024, 1, 11, 9, 52, 15, 0, ZoneOffset.ofHours(9)),
						"ECONOMY", "https://www.yna.co.kr/view/AKR20240111")));
	}

	@Test
	void 추천_상세를_조회한다() throws Exception {
		given(recommendationDetailService.getDetail(USER_ID, 10241L)).willReturn(detail());

		mockMvc.perform(get(PATH + "/10241").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.userRecommendationId").value(10241))
				.andExpect(jsonPath("$.data.label").value("한국은행 1월 기준금리 동결"))
				.andExpect(jsonPath("$.data.contextSummary").value("금통위가 기준금리를 동결했다."))
				.andExpect(jsonPath("$.data.articles[0].articleId").value(930001))
				.andExpect(jsonPath("$.data.articles[0].organizationName").value("연합뉴스"))
				.andExpect(jsonPath("$.data.articles[0].originalUrl")
						.value("https://www.yna.co.kr/view/AKR20240111"));
	}

	@Test
	void 없거나_남의_추천이면_404다() throws Exception {
		given(recommendationDetailService.getDetail(USER_ID, 10241L))
				.willThrow(new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND));

		mockMvc.perform(get(PATH + "/10241").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));
	}

	@Test
	void 상세도_토큰이_없으면_401이다() throws Exception {
		mockMvc.perform(get(PATH + "/10241")).andExpect(status().isUnauthorized());

		verify(recommendationDetailService, never()).getDetail(anyLong(), anyLong());
	}

	@Test
	void 상세_ID가_숫자가_아니면_400이다() throws Exception {
		mockMvc.perform(get(PATH + "/abc").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest());

		verify(recommendationDetailService, never()).getDetail(anyLong(), anyLong());
	}

	@Test
	void 요약이_없으면_null_로_내려간다() throws Exception {
		given(recommendationDetailService.getDetail(USER_ID, 10241L)).willReturn(
				new RecommendationDetailResponse(10241L, "00000020-0920-4000-8000-000000000001",
						"한국은행 1월 기준금리 동결", TopicCode.ECONOMY, null, List.of()));

		mockMvc.perform(get(PATH + "/10241").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.contextSummary").doesNotExist())
				.andExpect(jsonPath("$.data.articles").isEmpty());
	}
}

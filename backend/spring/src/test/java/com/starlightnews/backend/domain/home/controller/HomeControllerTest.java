package com.starlightnews.backend.domain.home.controller;

import java.time.OffsetDateTime;
import java.util.List;

import com.starlightnews.backend.domain.home.dto.HomeResponse;
import com.starlightnews.backend.domain.home.exception.HomeErrorCode;
import com.starlightnews.backend.domain.home.service.HomeService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.enums.NodeType;
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

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(HomeController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class HomeControllerTest {

	private static final String HOME_PATH = "/api/v1/home";
	private static final String NODE_ID = "00000020-0920-4000-8000-000000000001";
	private static final String REQUEST_ID = "550e8400-e29b-41d4-a716-446655440000";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private HomeService homeService;

	@Test
	void 비회원도_트렌드와_요청_ID를_조회한다() throws Exception {
		given(homeService.getHome()).willReturn(sampleHome());

		mockMvc.perform(get(HOME_PATH).header(RequestIdFilter.HEADER_NAME, REQUEST_ID))
				.andExpect(status().isOk())
				.andExpect(header().string(RequestIdFilter.HEADER_NAME, REQUEST_ID))
				.andExpect(jsonPath("$.meta.requestId").value(REQUEST_ID))
				.andExpect(jsonPath("$.data.snapshotAt").value("2026-09-15T18:00:00+09:00"))
				.andExpect(jsonPath("$.data.trends.length()").value(1))
				.andExpect(jsonPath("$.data.trends[0].trendItemId").value(101))
				.andExpect(jsonPath("$.data.trends[0].rank").value(1))
				.andExpect(jsonPath("$.data.trends[0].nodeType").value("EVENT"))
				.andExpect(jsonPath("$.data.trends[0].nodeKey").value(NODE_ID))
				.andExpect(jsonPath("$.data.trends[0].label").value("한국은행 기준금리 동결"))
				.andExpect(jsonPath("$.data.trends[0].articleCount").value(23))
				.andExpect(jsonPath("$.data.trendSnapshotId").doesNotExist())
				.andExpect(jsonPath("$.data.trends[0].growthRate").doesNotExist())
				.andExpect(jsonPath("$.data.trends[0].trendScore").doesNotExist());

		verify(homeService).getHome();
	}

	@Test
	void 로그인_사용자도_동일한_공개_응답을_조회한다() throws Exception {
		given(homeService.getHome()).willReturn(sampleHome());

		mockMvc.perform(get(HOME_PATH)
						.header(HttpHeaders.AUTHORIZATION, "Bearer " + jwtProvider.createAccessToken(1L)))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.trends[0].nodeKey").value(NODE_ID))
				.andExpect(jsonPath("$.data.trends[0].bookmarked").doesNotExist());
	}

	@Test
	void 잘못된_토큰이_있어도_공개_API를_조회할_수_있다() throws Exception {
		given(homeService.getHome()).willReturn(sampleHome());

		mockMvc.perform(get(HOME_PATH).header(HttpHeaders.AUTHORIZATION, "Bearer garbage"))
				.andExpect(status().isOk());
	}

	@Test
	void 데이터가_없어도_200과_null_시각_및_빈_배열을_응답한다() throws Exception {
		given(homeService.getHome()).willReturn(new HomeResponse(null, List.of()));

		mockMvc.perform(get(HOME_PATH))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.snapshotAt").hasJsonPath())
				.andExpect(jsonPath("$.data.snapshotAt").value(nullValue()))
				.andExpect(jsonPath("$.data.trends").isEmpty())
				.andExpect(jsonPath("$.meta.requestId").isString());
	}

	@Test
	void 홈_조회_실패는_500_HOME_DATA_FETCH_FAILED를_응답한다() throws Exception {
		given(homeService.getHome()).willThrow(new BusinessException(HomeErrorCode.HOME_DATA_FETCH_FAILED));

		mockMvc.perform(get(HOME_PATH))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.code").value("HOME_DATA_FETCH_FAILED"))
				.andExpect(jsonPath("$.path").value(HOME_PATH))
				.andExpect(jsonPath("$.requestId").isString());
	}

	private HomeResponse sampleHome() {
		return new HomeResponse(
				OffsetDateTime.parse("2026-09-15T18:00:00+09:00"),
				List.of(new HomeResponse.Item(101L, 1, NodeType.EVENT, NODE_ID, "한국은행 기준금리 동결", 23)));
	}
}

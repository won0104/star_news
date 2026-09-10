package com.starlightnews.backend.domain.graph.controller;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.graph.dto.GraphNodeDetailResponse;
import com.starlightnews.backend.domain.graph.dto.RelatedArticlesResponse;
import com.starlightnews.backend.domain.graph.service.GraphArticleService;
import com.starlightnews.backend.domain.graph.service.GraphNodeService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
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
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(GraphController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class GraphControllerTest {

	private static final String NODE_KEY = "00000020-0920-4000-8000-000000000001";
	private static final String PATH = "/api/v1/graphs/nodes/EVENT/" + NODE_KEY;

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private GraphNodeService graphNodeService;

	@MockitoBean
	private GraphArticleService graphArticleService;

	private static final String ARTICLES_PATH = "/api/v1/graphs/nodes/EVENT/" + NODE_KEY + "/articles";

	private GraphNodeDetailResponse sampleResponse(boolean bookmarked) {
		return new GraphNodeDetailResponse("EVENT", NODE_KEY, "한국은행 기준금리 동결", null,
				OffsetDateTime.of(2024, 1, 11, 9, 0, 0, 0, ZoneOffset.ofHours(9)), bookmarked);
	}

	private RelatedArticlesResponse sampleArticles() {
		return new RelatedArticlesResponse(
				List.of(new RelatedArticlesResponse.Item(930001L, "한국은행 1월 기준금리 동결", "연합뉴스",
						OffsetDateTime.of(2024, 1, 11, 9, 52, 15, 0, ZoneOffset.ofHours(9)), false)),
				18L, 1, true, "opaque-cursor");
	}

	@Test
	void 노드_상세_조회_성공시_200과_data_meta_구조로_응답한다() throws Exception {
		given(graphNodeService.getNodeDetail(any(NodeType.class), anyString(), any()))
				.willReturn(sampleResponse(false));

		mockMvc.perform(get(PATH))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.nodeType").value("EVENT"))
				.andExpect(jsonPath("$.data.nodeKey").value(NODE_KEY))
				.andExpect(jsonPath("$.data.title").value("한국은행 기준금리 동결"))
				.andExpect(jsonPath("$.data.type").doesNotExist())
				.andExpect(jsonPath("$.data.time").value("2024-01-11T09:00:00+09:00"))
				.andExpect(jsonPath("$.data.bookmarked").value(false))
				.andExpect(jsonPath("$.meta.requestId").isString());

		verify(graphNodeService).getNodeDetail(eq(NodeType.EVENT), eq(NODE_KEY), isNull());
	}

	@Test
	void 유효한_토큰이_있으면_서비스에_userId를_전달한다() throws Exception {
		given(graphNodeService.getNodeDetail(any(NodeType.class), anyString(), any()))
				.willReturn(sampleResponse(true));
		String accessToken = jwtProvider.createAccessToken(1L);

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.bookmarked").value(true));

		verify(graphNodeService).getNodeDetail(eq(NodeType.EVENT), eq(NODE_KEY), eq(1L));
	}

	@Test
	void 알_수_없는_nodeType은_400_INVALID_NODE_TYPE를_응답한다() throws Exception {
		mockMvc.perform(get("/api/v1/graphs/nodes/UNKNOWN/" + NODE_KEY))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_NODE_TYPE"));

		verify(graphNodeService, never()).getNodeDetail(any(), any(), any());
	}

	@Test
	void ARTICLE은_상세조회_대상이_아니라_400_INVALID_NODE_TYPE를_응답한다() throws Exception {
		mockMvc.perform(get("/api/v1/graphs/nodes/ARTICLE/" + NODE_KEY))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_NODE_TYPE"));

		verify(graphNodeService, never()).getNodeDetail(any(), any(), any());
	}

	@Test
	void 서비스가_RESOURCE_NOT_FOUND를_던지면_404를_응답한다() throws Exception {
		given(graphNodeService.getNodeDetail(any(NodeType.class), anyString(), any()))
				.willThrow(new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND));

		mockMvc.perform(get(PATH))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));
	}

	@Test
	void 서비스가_GRAPH_NODE_QUERY_FAILED를_던지면_500을_응답한다() throws Exception {
		given(graphNodeService.getNodeDetail(any(NodeType.class), anyString(), any()))
				.willThrow(new BusinessException(GraphErrorCode.GRAPH_NODE_QUERY_FAILED));

		mockMvc.perform(get(PATH))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.code").value("GRAPH_NODE_QUERY_FAILED"));
	}

	// --- 관련 기사 조회 ---

	@Test
	void 관련_기사_조회_성공시_200과_목록_페이징_구조로_응답한다() throws Exception {
		given(graphArticleService.getRelatedArticles(any(NodeType.class), anyString(), anyInt(), any(), any()))
				.willReturn(sampleArticles());

		mockMvc.perform(get(ARTICLES_PATH))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.articles[0].articleId").value(930001))
				.andExpect(jsonPath("$.data.articles[0].title").value("한국은행 1월 기준금리 동결"))
				.andExpect(jsonPath("$.data.articles[0].organizationName").value("연합뉴스"))
				.andExpect(jsonPath("$.data.articles[0].publishedAt").value("2024-01-11T09:52:15+09:00"))
				.andExpect(jsonPath("$.data.articles[0].bookmarked").value(false))
				.andExpect(jsonPath("$.data.totalCount").value(18))
				.andExpect(jsonPath("$.data.returnedCount").value(1))
				.andExpect(jsonPath("$.data.hasNext").value(true))
				.andExpect(jsonPath("$.data.nextCursor").value("opaque-cursor"))
				.andExpect(jsonPath("$.meta.requestId").isString());

		verify(graphArticleService).getRelatedArticles(eq(NodeType.EVENT), eq(NODE_KEY), eq(30), isNull(), isNull());
	}

	@Test
	void size와_cursor_쿼리파라미터를_서비스에_전달한다() throws Exception {
		given(graphArticleService.getRelatedArticles(any(NodeType.class), anyString(), anyInt(), any(), any()))
				.willReturn(sampleArticles());

		mockMvc.perform(get(ARTICLES_PATH).param("size", "5").param("cursor", "opaque-cursor"))
				.andExpect(status().isOk());

		verify(graphArticleService).getRelatedArticles(
				eq(NodeType.EVENT), eq(NODE_KEY), eq(5), eq("opaque-cursor"), isNull());
	}

	@Test
	void 유효한_토큰이_있으면_관련_기사_조회에도_userId를_전달한다() throws Exception {
		given(graphArticleService.getRelatedArticles(any(NodeType.class), anyString(), anyInt(), any(), any()))
				.willReturn(sampleArticles());
		String accessToken = jwtProvider.createAccessToken(1L);

		mockMvc.perform(get(ARTICLES_PATH).header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken))
				.andExpect(status().isOk());

		verify(graphArticleService).getRelatedArticles(eq(NodeType.EVENT), eq(NODE_KEY), eq(30), isNull(), eq(1L));
	}

	@Test
	void size가_1미만이면_400_INVALID_INPUT_VALUE를_응답한다() throws Exception {
		mockMvc.perform(get(ARTICLES_PATH).param("size", "0"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));

		verify(graphArticleService, never()).getRelatedArticles(any(), any(), anyInt(), any(), any());
	}

	@Test
	void size가_30초과면_400_INVALID_INPUT_VALUE를_응답한다() throws Exception {
		mockMvc.perform(get(ARTICLES_PATH).param("size", "31"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));
	}

	@Test
	void STORY는_관련_기사_대상이_아니라_400_INVALID_NODE_TYPE를_응답한다() throws Exception {
		mockMvc.perform(get("/api/v1/graphs/nodes/STORY/" + NODE_KEY + "/articles"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_NODE_TYPE"));

		verify(graphArticleService, never()).getRelatedArticles(any(), any(), anyInt(), any(), any());
	}

	@Test
	void 서비스가_INVALID_CURSOR를_던지면_400을_응답한다() throws Exception {
		given(graphArticleService.getRelatedArticles(any(NodeType.class), anyString(), anyInt(), any(), any()))
				.willThrow(new BusinessException(GraphErrorCode.INVALID_CURSOR));

		mockMvc.perform(get(ARTICLES_PATH).param("cursor", "broken"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_CURSOR"));
	}

	@Test
	void 관련_기사_조회에서_노드가_없으면_404를_응답한다() throws Exception {
		given(graphArticleService.getRelatedArticles(any(NodeType.class), anyString(), anyInt(), any(), any()))
				.willThrow(new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND));

		mockMvc.perform(get(ARTICLES_PATH))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));
	}
}

package com.starlightnews.backend.domain.graph.controller;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;

import com.starlightnews.backend.domain.graph.dto.GraphNodeDetailResponse;
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

	private GraphNodeDetailResponse sampleResponse(boolean bookmarked) {
		return new GraphNodeDetailResponse("EVENT", NODE_KEY, "한국은행 기준금리 동결", null,
				OffsetDateTime.of(2024, 1, 11, 9, 0, 0, 0, ZoneOffset.ofHours(9)), bookmarked);
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
}

package com.starlightnews.backend.domain.user.controller;

import com.starlightnews.backend.domain.user.service.GraphNodeClickService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(UserGraphController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class UserGraphControllerTest {

	private static final String NODE_KEY = "00000024-0920-4000-8000-000000000001";
	private static final String CLICKS_PATH = "/api/v1/users/me/graph/nodes/ENTITY/" + NODE_KEY + "/clicks";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private GraphNodeClickService graphNodeClickService;

	private String bearer() {
		return "Bearer " + jwtProvider.createAccessToken(1L);
	}

	@Test
	void 클릭_기록_성공시_200과_data_null로_응답한다() throws Exception {
		mockMvc.perform(post(CLICKS_PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data").value(nullValue()))
				.andExpect(jsonPath("$.meta.requestId").isString());

		verify(graphNodeClickService).recordClick(eq(1L), eq(NodeType.ENTITY), eq(NODE_KEY));
	}

	@Test
	void 토큰이_없으면_401이고_서비스를_호출하지_않는다() throws Exception {
		mockMvc.perform(post(CLICKS_PATH))
				.andExpect(status().isUnauthorized());

		verify(graphNodeClickService, never()).recordClick(anyLong(), any(), anyString());
	}

	@Test
	void 알_수_없는_nodeType은_400_INVALID_NODE_TYPE를_응답한다() throws Exception {
		mockMvc.perform(post("/api/v1/users/me/graph/nodes/UNKNOWN/" + NODE_KEY + "/clicks")
						.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_NODE_TYPE"));

		verify(graphNodeClickService, never()).recordClick(anyLong(), any(), anyString());
	}

	@Test
	void TOPIC은_개인그래프_대상이_아니라_400_INVALID_NODE_TYPE를_응답한다() throws Exception {
		mockMvc.perform(post("/api/v1/users/me/graph/nodes/TOPIC/" + NODE_KEY + "/clicks")
						.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_NODE_TYPE"));

		verify(graphNodeClickService, never()).recordClick(anyLong(), any(), anyString());
	}

	@Test
	void 서비스가_RESOURCE_NOT_FOUND를_던지면_404를_응답한다() throws Exception {
		willThrow(new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND))
				.given(graphNodeClickService).recordClick(anyLong(), any(), anyString());

		mockMvc.perform(post(CLICKS_PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));
	}
}

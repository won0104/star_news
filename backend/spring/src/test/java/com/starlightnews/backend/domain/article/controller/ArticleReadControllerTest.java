package com.starlightnews.backend.domain.article.controller;

import com.starlightnews.backend.domain.user.service.ArticleReadService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import com.starlightnews.backend.global.security.InMemoryTokenBlacklist;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ArticleReadController.class)
@org.springframework.context.annotation.Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class ArticleReadControllerTest {

	private static final String READS_PATH = "/api/v1/articles/{articleId}/reads";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private ArticleReadService articleReadService;

	private String bearer() {
		return "Bearer " + jwtProvider.createAccessToken(1L);
	}

	@Test
	void 열람기록_저장_성공시_204와_빈_본문을_응답한다() throws Exception {
		mockMvc.perform(post(READS_PATH, 930001L).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isNoContent())
				.andExpect(content().string(""));

		verify(articleReadService).recordRead(eq(1L), eq(930001L));
	}

	@Test
	void Access_Token이_없으면_401을_응답한다() throws Exception {
		mockMvc.perform(post(READS_PATH, 930001L))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"));

		verify(articleReadService, never()).recordRead(any(), any());
	}

	@Test
	void articleId가_숫자가_아니면_400_TYPE_MISMATCH를_응답한다() throws Exception {
		// PathVariable 형식 오류는 GlobalExceptionHandler 가 프로젝트 공통으로 TYPE_MISMATCH 로 변환한다.
		mockMvc.perform(post(READS_PATH, "not-a-number").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("TYPE_MISMATCH"));

		verify(articleReadService, never()).recordRead(any(), any());
	}

	@Test
	void 서비스가_RESOURCE_NOT_FOUND를_던지면_404를_응답한다() throws Exception {
		willThrow(new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND))
				.given(articleReadService).recordRead(anyLong(), anyLong());

		mockMvc.perform(post(READS_PATH, 999999L).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));
	}

	@Test
	void 서비스가_INTERNAL_SERVER_ERROR를_던지면_500을_응답한다() throws Exception {
		willThrow(new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR))
				.given(articleReadService).recordRead(anyLong(), anyLong());

		mockMvc.perform(post(READS_PATH, 930001L).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.code").value("INTERNAL_SERVER_ERROR"));
	}
}

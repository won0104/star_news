package com.starlightnews.backend.domain.search.controller;

import java.util.List;

import com.starlightnews.backend.domain.search.dto.SearchRequest;
import com.starlightnews.backend.domain.search.dto.SearchResultItem;
import com.starlightnews.backend.domain.search.service.SearchService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.response.CursorResponse;
import com.starlightnews.backend.global.security.InMemoryTokenBlacklist;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(SearchController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class SearchControllerTest {

	private static final String PATH = "/api/v1/search";

	@Autowired
	private MockMvc mockMvc;

	@MockitoBean
	private SearchService searchService;

	@Test
	void 비회원이_검색하면_결과와_cursor와_requestId를_응답한다() throws Exception {
		given(searchService.search(any())).willReturn(CursorResponse.of(
				List.of(new SearchResultItem("EVENT", "event-1", "한국은행 기준금리 동결")),
				true, "next-cursor"));

		mockMvc.perform(get(PATH).param("query", "한국은행이 금리를 동결했다"))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.items[0].nodeType").value("EVENT"))
				.andExpect(jsonPath("$.data.items[0].nodeKey").value("event-1"))
				.andExpect(jsonPath("$.data.items[0].label").value("한국은행 기준금리 동결"))
				.andExpect(jsonPath("$.data.hasNext").value(true))
				.andExpect(jsonPath("$.data.nextCursor").value("next-cursor"))
				.andExpect(jsonPath("$.meta.requestId").isString());

		verify(searchService).search(new SearchRequest("한국은행이 금리를 동결했다", null, 20));
	}

	@Test
	void size와_cursor를_서비스에_전달한다() throws Exception {
		given(searchService.search(any())).willReturn(CursorResponse.of(List.of(), false, null));

		mockMvc.perform(get(PATH)
						.param("query", "한국은행")
						.param("cursor", "opaque-cursor")
						.param("size", "5"))
				.andExpect(status().isOk());

		verify(searchService).search(new SearchRequest("한국은행", "opaque-cursor", 5));
	}

	@Test
	void 결과가_없어도_200과_빈_items를_응답한다() throws Exception {
		given(searchService.search(any())).willReturn(CursorResponse.of(List.of(), false, null));

		mockMvc.perform(get(PATH).param("query", "없는 검색어"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items").isEmpty())
				.andExpect(jsonPath("$.data.hasNext").value(false))
				.andExpect(jsonPath("$.data.nextCursor").doesNotExist());
	}

	@Test
	void query가_누락되거나_공백이면_400_INVALID_REQUEST() throws Exception {
		mockMvc.perform(get(PATH))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

		mockMvc.perform(get(PATH).param("query", "   "))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

		verifyNoInteractions(searchService);
	}

	@Test
	void size가_숫자가_아니거나_범위를_벗어나면_400_INVALID_REQUEST() throws Exception {
		mockMvc.perform(get(PATH).param("query", "검색").param("size", "abc"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

		mockMvc.perform(get(PATH).param("query", "검색").param("size", "0"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

		mockMvc.perform(get(PATH).param("query", "검색").param("size", "51"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

		verify(searchService, never()).search(any());
	}
}

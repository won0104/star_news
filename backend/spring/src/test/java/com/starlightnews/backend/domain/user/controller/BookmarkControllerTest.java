package com.starlightnews.backend.domain.user.controller;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.user.dto.ArticleBookmarkItem;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksRequest;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksResponse;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksResponse.ArticleBookmarkResult;
import com.starlightnews.backend.domain.user.exception.UserErrorCode;
import com.starlightnews.backend.domain.user.service.BookmarkService;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.response.CursorResponse;
import com.starlightnews.backend.global.security.InMemoryTokenBlacklist;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(BookmarkController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class BookmarkControllerTest {

	private static final String PATH = "/api/v1/users/me/bookmarks/articles";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private BookmarkService bookmarkService;

	@Test
	void 조회_성공시_기사목록과_페이지정보와_requestId를_응답한다() throws Exception {
		OffsetDateTime publishedAt = OffsetDateTime.of(
				2026, 8, 31, 9, 0, 0, 0, ZoneOffset.UTC);
		OffsetDateTime bookmarkedAt = OffsetDateTime.of(
				2026, 9, 1, 9, 0, 0, 0, ZoneOffset.ofHours(9));
		given(bookmarkService.getArticleBookmarks(1L, null, 20))
				.willReturn(CursorResponse.of(List.of(new ArticleBookmarkItem(
						101L, "기사 제목", "연합뉴스", publishedAt, "핵심 요약", bookmarkedAt)),
						true, "opaque-cursor"));

		mockMvc.perform(get(PATH).header(HttpHeaders.AUTHORIZATION, bearer(1L)))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.items[0].articleId").value(101))
				.andExpect(jsonPath("$.data.items[0].title").value("기사 제목"))
				.andExpect(jsonPath("$.data.items[0].publisher").value("연합뉴스"))
				.andExpect(jsonPath("$.data.items[0].publishedAt").value("2026-08-31T09:00:00Z"))
				.andExpect(jsonPath("$.data.items[0].summary").value("핵심 요약"))
				.andExpect(jsonPath("$.data.items[0].bookmarkedAt").value("2026-09-01T09:00:00+09:00"))
				.andExpect(jsonPath("$.data.hasNext").value(true))
				.andExpect(jsonPath("$.data.nextCursor").value("opaque-cursor"))
				.andExpect(jsonPath("$.meta.requestId").isString());

		verify(bookmarkService).getArticleBookmarks(1L, null, 20);
	}

	@Test
	void cursor와_size를_서비스에_전달한다() throws Exception {
		given(bookmarkService.getArticleBookmarks(1L, "cursor-value", 5))
				.willReturn(CursorResponse.of(List.of(), false, null));

		mockMvc.perform(get(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.param("cursor", "cursor-value")
						.param("size", "5"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.items").isEmpty())
				.andExpect(jsonPath("$.data.hasNext").value(false))
				.andExpect(jsonPath("$.data.nextCursor").doesNotExist());

		verify(bookmarkService).getArticleBookmarks(1L, "cursor-value", 5);
	}

	@Test
	void size가_허용범위를_벗어나면_400_INVALID_INPUT_VALUE이다() throws Exception {
		mockMvc.perform(get(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.param("size", "101"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));

		verify(bookmarkService, never()).getArticleBookmarks(anyLong(), anyString(), anyInt());
		verify(bookmarkService, never()).getArticleBookmarks(anyLong(), isNull(), anyInt());
	}

	@Test
	void 서비스가_INVALID_CURSOR를_던지면_400이다() throws Exception {
		given(bookmarkService.getArticleBookmarks(1L, "bad", 20))
				.willThrow(new BusinessException(UserErrorCode.INVALID_CURSOR));

		mockMvc.perform(get(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.param("cursor", "bad"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_CURSOR"));
	}

	@Test
	void 인증_토큰이_없으면_401_UNAUTHORIZED이다() throws Exception {
		mockMvc.perform(get(PATH))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"));

		verify(bookmarkService, never()).getArticleBookmarks(anyLong(), isNull(), anyInt());
	}

	@Test
	void 기사_북마크_변경_성공시_요청순서의_최종상태와_requestId를_응답한다() throws Exception {
		given(bookmarkService.updateArticleBookmarks(eq(1L), any(UpdateArticleBookmarksRequest.class)))
				.willReturn(new UpdateArticleBookmarksResponse(List.of(
						new ArticleBookmarkResult(101L, true),
						new ArticleBookmarkResult(102L, false))));

		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.contentType(MediaType.APPLICATION_JSON)
						.content("""
								{"changes":[
								  {"articleId":101,"bookmarked":true},
								  {"articleId":102,"bookmarked":false}
								]}"""))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.results[0].articleId").value(101))
				.andExpect(jsonPath("$.data.results[0].bookmarked").value(true))
				.andExpect(jsonPath("$.data.results[1].articleId").value(102))
				.andExpect(jsonPath("$.data.results[1].bookmarked").value(false))
				.andExpect(jsonPath("$.meta.requestId").isString());

		verify(bookmarkService).updateArticleBookmarks(eq(1L), any(UpdateArticleBookmarksRequest.class));
	}

	@Test
	void changes가_누락되면_400_INVALID_INPUT_VALUE이다() throws Exception {
		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));

		verify(bookmarkService, never()).updateArticleBookmarks(anyLong(), any());
	}

	@Test
	void 변경항목의_필드가_누락되면_400_INVALID_INPUT_VALUE이다() throws Exception {
		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"changes\":[{\"articleId\":101}]}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));

		verify(bookmarkService, never()).updateArticleBookmarks(anyLong(), any());
	}

	@Test
	void 서비스가_EMPTY_CHANGES를_던지면_400이다() throws Exception {
		given(bookmarkService.updateArticleBookmarks(eq(1L), any(UpdateArticleBookmarksRequest.class)))
				.willThrow(new BusinessException(UserErrorCode.EMPTY_CHANGES));

		mockMvc.perform(patch(PATH)
						.header(HttpHeaders.AUTHORIZATION, bearer(1L))
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"changes\":[]}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("EMPTY_CHANGES"));
	}

	@Test
	void 기사_북마크_변경시_인증토큰이_없으면_401_UNAUTHORIZED이다() throws Exception {
		mockMvc.perform(patch(PATH)
						.contentType(MediaType.APPLICATION_JSON)
						.content("{\"changes\":[{\"articleId\":101,\"bookmarked\":true}]}"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"));

		verify(bookmarkService, never()).updateArticleBookmarks(anyLong(), any());
	}

	private String bearer(long userId) {
		return "Bearer " + jwtProvider.createAccessToken(userId);
	}
}

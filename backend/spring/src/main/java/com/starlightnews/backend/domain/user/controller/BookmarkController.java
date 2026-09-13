package com.starlightnews.backend.domain.user.controller;

import com.starlightnews.backend.domain.user.dto.ArticleBookmarkItem;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksRequest;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksResponse;
import com.starlightnews.backend.domain.user.service.BookmarkService;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.error.ErrorResponse;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.response.ApiResponse;
import com.starlightnews.backend.global.response.CursorResponse;
import com.starlightnews.backend.global.security.AuthenticatedUser;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "북마크", description = "사용자 기사·그래프 Node 북마크")
@RestController
@Validated
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/users/me/bookmarks")
public class BookmarkController {

	private final BookmarkService bookmarkService;

	@Operation(
			summary = "북마크 기사 목록 조회",
			description = "북마크한 공개 기사를 최신 등록순으로 조회한다. **Access Token 필요.**")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "size 범위 위반(INVALID_INPUT_VALUE) / 잘못된 cursor(INVALID_CURSOR)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "사용자를 찾을 수 없음 (code: USER_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping("/articles")
	public ApiResponse<CursorResponse<ArticleBookmarkItem>> getArticleBookmarks(
			@Parameter(description = "더 보기 커서 (직전 응답의 nextCursor)")
			@RequestParam(required = false) String cursor,
			@Parameter(description = "이번 응답 최대 기사 수 (1~100)", example = "20")
			@RequestParam(defaultValue = "20") @Min(1) @Max(100) int size,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(
				bookmarkService.getArticleBookmarks(user.userId(), cursor, size), requestId);
	}

	@Operation(
			summary = "기사 북마크 상태 변경",
			description = "한 개 또는 여러 기사의 북마크 최종 상태를 하나의 트랜잭션으로 변경한다. **Access Token 필요.**")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "변경 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "입력값 오류 (code: INVALID_INPUT_VALUE / EMPTY_CHANGES / DUPLICATED_ARTICLE_CHANGE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "사용자 또는 북마크 가능한 기사를 찾을 수 없음 (code: USER_NOT_FOUND / ARTICLE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@PatchMapping("/articles")
	public ApiResponse<UpdateArticleBookmarksResponse> updateArticleBookmarks(
			@Valid @RequestBody UpdateArticleBookmarksRequest request,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(
				bookmarkService.updateArticleBookmarks(user.userId(), request), requestId);
	}
}

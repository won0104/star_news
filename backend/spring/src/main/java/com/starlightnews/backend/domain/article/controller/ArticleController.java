package com.starlightnews.backend.domain.article.controller;

import com.starlightnews.backend.domain.article.dto.ArticleDetailResponse;
import com.starlightnews.backend.domain.article.service.ArticleDetailService;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.error.ErrorResponse;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.response.ApiResponse;
import com.starlightnews.backend.global.security.AuthenticatedUser;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "기사", description = "기사 상세 조회")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/articles")
public class ArticleController {

	private final ArticleDetailService articleDetailService;

	@Operation(
			summary = "기사 상세 조회",
			description = """
					기사 정보, 저장된 AI 요약과 상태, 언론사 원문 주소를 조회한다. 인증 불필요.
					유효한 Access Token이 있으면 현재 사용자의 기사 북마크 여부를 함께 반환한다.
					이 API는 요약을 생성하거나 외부 API를 호출하지 않는다.""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "articleId 형식 오류 (code: TYPE_MISMATCH)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "기사를 찾을 수 없음 (code: ARTICLE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500",
					description = "기사 상세 조회 실패 (code: ARTICLE_DETAIL_QUERY_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@GetMapping("/{articleId}")
	public ApiResponse<ArticleDetailResponse> getArticleDetail(
			@Parameter(description = "기사 ID", example = "101") @PathVariable Long articleId,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		Long userId = user != null ? user.userId() : null;
		return ApiResponse.success(articleDetailService.getDetail(articleId, userId), requestId);
	}
}

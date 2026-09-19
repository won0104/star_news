package com.starlightnews.backend.domain.article.controller;

import com.starlightnews.backend.domain.article.dto.ArticleDetailResponse;
import com.starlightnews.backend.domain.article.dto.ArticleSummaryResponse;
import com.starlightnews.backend.domain.article.dto.ArticleSummaryStatus;
import com.starlightnews.backend.domain.article.service.ArticleDetailService;
import com.starlightnews.backend.domain.article.service.ArticleSummaryService;
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
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "기사", description = "기사 상세 조회 및 요약 생성")
@RestController
@RequiredArgsConstructor
@RequestMapping(value = ApiPaths.API_V1 + "/articles", produces = MediaType.APPLICATION_JSON_VALUE)
public class ArticleController {

	private final ArticleDetailService articleDetailService;
	private final ArticleSummaryService articleSummaryService;

	@Operation(
			summary = "기사 상세 조회",
			description = """
					기사 정보, AI 요약과 상태, 언론사 원문 주소를 조회한다. 인증 불필요.
					유효한 Access Token이 있으면 현재 사용자의 기사 북마크 여부를 함께 반환한다.
					저장된 요약이 없으면 GMS로 요약을 생성해 저장한 뒤 반환한다.
					다른 요청이 이미 생성 중이면 summary=null, summaryStatus=PROCESSING을 반환한다.""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "articleId 형식 오류 (code: TYPE_MISMATCH)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "기사를 찾을 수 없음 (code: ARTICLE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "422",
					description = "요약할 본문 없음 (code: ARTICLE_CONTENT_UNAVAILABLE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "502",
					description = "GMS 호출 또는 응답 처리 실패 (code: SUMMARY_GENERATION_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500",
					description = "기사 상세 조회 또는 요약 저장 실패 "
							+ "(code: ARTICLE_DETAIL_QUERY_FAILED, SUMMARY_SAVE_FAILED)",
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

	@Operation(
			summary = "기사 요약 생성",
			description = """
					저장된 요약이 없을 때 GMS로 생성해 MySQL에 저장한다. 인증 불필요.
					기존 요약은 재사용하고, 다른 요청이 생성 중이면 중복 호출 없이 PROCESSING을 반환한다.""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200",
					description = "생성 완료 또는 기존 요약 반환"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "202",
					description = "다른 요청이 요약 생성 중"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "articleId 형식 오류 (code: TYPE_MISMATCH)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "기사 없음 또는 분석 미완료 (code: ARTICLE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "422",
					description = "요약할 본문 없음 (code: ARTICLE_CONTENT_UNAVAILABLE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "502",
					description = "GMS 호출 또는 응답 처리 실패 (code: SUMMARY_GENERATION_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500",
					description = "생성한 요약 저장 실패 (code: SUMMARY_SAVE_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@PostMapping("/{articleId}/summary")
	public ResponseEntity<ApiResponse<ArticleSummaryResponse>> generateArticleSummary(
			@Parameter(description = "기사 ID", example = "101") @PathVariable Long articleId,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		ArticleSummaryResponse response = articleSummaryService.generate(articleId);
		HttpStatus status = response.summaryStatus() == ArticleSummaryStatus.PROCESSING
				? HttpStatus.ACCEPTED : HttpStatus.OK;
		return ResponseEntity.status(status).body(ApiResponse.success(response, requestId));
	}
}

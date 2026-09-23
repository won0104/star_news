package com.starlightnews.backend.domain.demo.controller;

import com.starlightnews.backend.domain.demo.dto.DemoArticleRequest;
import com.starlightnews.backend.domain.demo.dto.DemoGraphResponse;
import com.starlightnews.backend.domain.demo.service.DemoArticleService;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.error.ErrorResponse;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.response.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * 시연용 기사 투입.
 *
 * <p>기사를 직접 붙여넣어 저장·분석하고, 그 기사에서 만들어진 지식그래프를 바로 돌려준다.
 * 수집·분석 배치를 기다리지 않고 그 자리에서 결과를 보여 주기 위한 경로다.
 */
@Tag(name = "Demo", description = "시연용 기사 투입과 지식그래프 조회")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/demo/articles")
public class DemoArticleController {

	private final DemoArticleService demoArticleService;

	@Operation(
			summary = "기사 투입 후 지식그래프 생성",
			description = """
					기사를 저장하고 그 자리에서 AI 분석을 돌린 뒤, 만들어진 그래프를 돌려준다.

					**응답까지 30~60초, 길면 150초까지 걸린다.** AI 워커의 추론을 기다리기 때문이다.
					호출하는 쪽의 타임아웃을 180초 이상으로 두어야 한다.""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "201",
					description = "저장·분석 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "제목·본문 누락 또는 본문이 100자 미만 (code: INVALID_INPUT_VALUE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "409",
					description = "같은 본문이 다른 제목으로 이미 있음 (code: DEMO_ARTICLE_NOT_STORED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "502",
					description = "분석 실패 (code: DEMO_ANALYSIS_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	public ApiResponse<DemoGraphResponse> createAndAnalyze(
			@Valid @RequestBody DemoArticleRequest request,
			@Parameter(description = "대표로 다루는 사건만 남길지. 기본값은 전부", example = "true")
			@RequestParam(defaultValue = "false") boolean primaryOnly,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(
				demoArticleService.createAndAnalyze(request, primaryOnly), requestId);
	}

	@Operation(
			summary = "기사의 지식그래프 조회",
			description = "이미 분석이 끝난 기사의 그래프를 다시 읽는다. 시연 기사가 아니어도 된다.")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200",
					description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "기사 없음 (code: DEMO_ARTICLE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "409",
					description = "아직 분석 전 (code: DEMO_ARTICLE_NOT_ANALYZED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@GetMapping("/{articleId}/graph")
	public ApiResponse<DemoGraphResponse> findGraph(
			@Parameter(description = "기사 ID", example = "11285") @PathVariable long articleId,
			@Parameter(description = "대표로 다루는 사건만 남길지. 기본값은 전부", example = "true")
			@RequestParam(defaultValue = "false") boolean primaryOnly,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(demoArticleService.findGraph(articleId, primaryOnly), requestId);
	}
}

package com.starlightnews.backend.domain.user.controller;

import com.starlightnews.backend.domain.user.dto.NewsReportResponse;
import com.starlightnews.backend.domain.user.service.NewsReportService;
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
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "사용자 뉴스 리포트", description = "최근 3개월 뉴스 열람 및 Node 탐색 통계")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/users/me/statistics")
public class NewsReportController {

	private final NewsReportService newsReportService;

	@Operation(
			summary = "나의 뉴스 리포트 조회",
			description = "최근 3개월 기사 열람과 Node 탐색 데이터를 MySQL에서 집계한다. **Access Token 필요.**")
	@ApiResponses({
		@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
		@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
				description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
				content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
		@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500",
				description = "뉴스 리포트 집계 실패 (code: NEWS_REPORT_AGGREGATION_FAILED)",
				content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping("/news-report")
	public ApiResponse<NewsReportResponse> getNewsReport(
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(newsReportService.getNewsReport(user.userId()), requestId);
	}
}

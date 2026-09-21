package com.starlightnews.backend.domain.user.controller;

import java.time.LocalDate;

import com.starlightnews.backend.domain.user.dto.ArticleHistoryResponse;
import com.starlightnews.backend.domain.user.service.ArticleHistoryService;
import com.starlightnews.backend.domain.user.support.GraphReadPeriod;
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
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "사용자 열람 기록", description = "사용자 전체 기사 열람 기록 조회")
@RestController
@Validated
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/users/me")
public class UserHistoryController {

	private final ArticleHistoryService articleHistoryService;

	@Operation(
			summary = "전체 열람 기록 조회",
			description = """
					사용자가 읽은 전체 기사를 최근 읽은 순(lastReadAt DESC)으로 조회한다. **Access Token 필요.**
					- topicCode 를 주면 그 Topic 만 필터링, 없으면 전체
					- from·to를 함께 지정하면 마지막으로 읽은 날짜가 해당 기간에 속한 기사만 반환 (KST, 양끝 포함)""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
				description = "지원하지 않는 topicCode(INVALID_TOPIC_CODE) / size·기간 오류(INVALID_INPUT_VALUE) / 잘못된 cursor(INVALID_CURSOR)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping("/history")
	public ApiResponse<ArticleHistoryResponse> getHistory(
			@Parameter(description = "필터링할 Topic 코드 (없으면 전체)", example = "ECONOMY")
			@RequestParam(required = false) String topicCode,
			@Parameter(description = "이번 응답 최대 기사 수 (1~50)", example = "20")
			@RequestParam(defaultValue = "20") @Min(1) @Max(50) int size,
			@Parameter(description = "더 보기 커서 (직전 응답의 nextCursor)")
			@RequestParam(required = false) String cursor,
			@Parameter(description = "마지막으로 읽은 날짜 시작 (포함, KST). to와 함께 지정", example = "2026-09-01")
			@RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
			@Parameter(description = "마지막으로 읽은 날짜 끝 (포함, KST). from과 함께 지정", example = "2026-09-30")
			@RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		GraphReadPeriod period = GraphReadPeriod.optional(from, to);
		return ApiResponse.success(
				period == null
						? articleHistoryService.getHistory(user.userId(), topicCode, size, cursor)
						: articleHistoryService.getHistory(user.userId(), topicCode, size, cursor, period), requestId);
	}
}

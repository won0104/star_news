package com.starlightnews.backend.domain.recommendation.controller;

import com.starlightnews.backend.domain.recommendation.dto.RecommendationBoardResponse;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationDetailResponse;
import com.starlightnews.backend.domain.recommendation.service.RecommendationBoardService;
import com.starlightnews.backend.domain.recommendation.service.RecommendationDetailService;
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
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "개인화 추천", description = "사전 계산된 추천 회차 조회")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/recommendations")
public class RecommendationController {

	private final RecommendationBoardService recommendationBoardService;
	private final RecommendationDetailService recommendationDetailService;

	@Operation(
			summary = "추천 보드 조회",
			description = """
					공개된 최신 추천 회차를 순위 순으로 조회한다. **Access Token 필요.**
					- 추천은 실시간 계산이 아니다. 05:30·17:30 에 계산해 06:00·18:00 에 공개한다
					- 공개 시각이 지나지 않은 회차는 보이지 않으므로 그 사이에는 직전 회차가 조회된다
					- 아직 공개된 회차가 없으면 회차 정보는 null 이고 목록은 비어 있다 (오류 아님)
					- 카드 링크에는 `eventId` 가 아니라 상세 API 키인 `userRecommendationId` 를 쓴다""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping
	public ApiResponse<RecommendationBoardResponse> getBoard(
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(recommendationBoardService.getBoard(user.userId()), requestId);
	}

	@Operation(
			summary = "추천 Event 상세 조회",
			description = """
					추천 카드 하나의 Event 정보와 관련 기사를 조회한다. **Access Token 필요.**
					- 보드 응답의 `userRecommendationId` 를 그대로 넘긴다. `eventId` 가 아니다
					- 관련 기사는 Event 와의 관련도가 높은 순이다
					- `contextSummary` 는 추천 배치가 회차를 저장한 직후에 만들어 둔 것을 읽기만 한다.
					  아직 만들어지지 않았거나 생성에 실패했으면 `null` 이므로 화면이 이를 정상 상태로 다뤄야 한다
					- 다른 사용자의 추천은 없는 것과 똑같이 404 로 응답한다""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "userRecommendationId 형식 오류 (code: TYPE_MISMATCH)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "추천을 찾을 수 없거나 다른 사용자의 추천 (code: RESOURCE_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping("/{userRecommendationId}")
	public ApiResponse<RecommendationDetailResponse> getDetail(
			@Parameter(description = "보드 응답의 추천 상세 조회 키", example = "10241")
			@PathVariable Long userRecommendationId,
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(
				recommendationDetailService.getDetail(user.userId(), userRecommendationId), requestId);
	}
}

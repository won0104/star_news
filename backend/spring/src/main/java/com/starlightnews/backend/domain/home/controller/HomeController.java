package com.starlightnews.backend.domain.home.controller;

import com.starlightnews.backend.domain.home.dto.HomeResponse;
import com.starlightnews.backend.domain.home.service.HomeService;
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
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 비회원과 로그인 사용자가 공통으로 사용하는 홈 트렌드 조회 API.
 */
@Tag(name = "홈", description = "오늘의 트렌드 조회")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/home")
public class HomeController {

	private final HomeService homeService;

	@Operation(
			summary = "홈 오늘의 트렌드 조회",
			description = """
					로그인 여부와 관계없이 공개된 최신 집계 회차의 오늘의 트렌드를 순위순으로 최대 10개 반환한다.
					05:00/17:00 KST 기준으로 집계한 결과를 06:00/18:00부터 조회한다.
					snapshotAt은 기사 집계 기준이 아닌 06:00/18:00 공개 회차 시각이다.
					공개된 트렌드가 없으면 snapshotAt은 null, trends는 빈 배열이다.
					이미 열린 화면은 공개 시각에 다시 요청해야 새 결과를 표시할 수 있다.
					요청 시 트렌드를 계산하지 않으며 그래프·개인화 정보는 포함하지 않는다.""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "500",
					description = "홈 데이터 조회 또는 조합 실패 (HOME_DATA_FETCH_FAILED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@GetMapping
	public ApiResponse<HomeResponse> getHome(
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(homeService.getHome(), requestId);
	}
}

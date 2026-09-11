package com.starlightnews.backend.domain.user.controller;

import com.starlightnews.backend.domain.user.dto.TopicPreferenceResponse;
import com.starlightnews.backend.domain.user.dto.UpdateTopicPreferenceRequest;
import com.starlightnews.backend.domain.user.service.TopicPreferenceService;
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
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "회원", description = "회원 정보 · 관심 분야 · 탈퇴")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/users/me/topic-preferences")
public class TopicPreferenceController {

	private final TopicPreferenceService topicPreferenceService;

	@Operation(
			summary = "관심 Topic 목록 조회",
			description = "현재 로그인한 사용자가 설정한 관심 Topic 목록을 조회한다. **Access Token 필요.**")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "사용자를 찾을 수 없음 (code: USER_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping("/interests")
	public ApiResponse<TopicPreferenceResponse> getInterests(
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(topicPreferenceService.getInterests(user.userId()), requestId);
	}

	@Operation(
			summary = "비관심 Topic 목록 조회",
			description = "현재 로그인한 사용자가 설정한 비관심 Topic 목록을 조회한다. **Access Token 필요.**")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "사용자를 찾을 수 없음 (code: USER_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping("/dislikes")
	public ApiResponse<TopicPreferenceResponse> getDislikes(
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(topicPreferenceService.getDislikes(user.userId()), requestId);
	}

	@Operation(
			summary = "관심 Topic 목록 일괄 변경",
			description = "요청한 Topic 목록을 현재 로그인 사용자의 최종 관심 목록으로 저장한다. **Access Token 필요.**")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "변경 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "입력값 오류 (code: INVALID_INPUT_VALUE / INVALID_TOPIC / DUPLICATED_TOPIC)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "사용자를 찾을 수 없음 (code: USER_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@PutMapping("/interests")
	public ApiResponse<TopicPreferenceResponse> replaceInterests(
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Valid @RequestBody UpdateTopicPreferenceRequest request,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(topicPreferenceService.replaceInterests(user.userId(), request), requestId);
	}
}

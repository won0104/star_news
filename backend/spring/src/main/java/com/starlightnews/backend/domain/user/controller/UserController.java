package com.starlightnews.backend.domain.user.controller;

import com.starlightnews.backend.domain.user.dto.UpdateNicknameRequest;
import com.starlightnews.backend.domain.user.dto.UserProfileResponse;
import com.starlightnews.backend.domain.user.dto.WithdrawalRequest;
import com.starlightnews.backend.domain.user.service.UserService;
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
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "회원", description = "회원 정보 · 관심 분야 · 탈퇴")
@RestController
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/users")
public class UserController {

	private static final String REFRESH_TOKEN_COOKIE = "refreshToken";
	private static final String REFRESH_TOKEN_COOKIE_PATH = ApiPaths.API_V1 + "/auth";

	private final UserService userService;

	@Operation(summary = "내 정보 조회",
			description = "현재 로그인한 사용자의 기본 정보와 관심·비관심 Topic 설정을 조회한다. Access Token 필요.")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "사용자를 찾을 수 없음 (code: USER_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@GetMapping("/me")
	public ApiResponse<UserProfileResponse> getMyProfile(
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(userService.getMyProfile(user.userId()), requestId);
	}

	@Operation(summary = "내 닉네임 수정",
			description = "현재 로그인한 사용자의 닉네임을 변경하고 최신 사용자 정보를 반환한다. Access Token 필요.")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "수정 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "닉네임 형식 오류 (code: INVALID_INPUT_VALUE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 오류 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404",
					description = "사용자를 찾을 수 없음 (code: USER_NOT_FOUND)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@PatchMapping("/me")
	public ApiResponse<UserProfileResponse> updateNickname(
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Valid @RequestBody UpdateNicknameRequest request,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(userService.updateNickname(user.userId(), request.nickname()), requestId);
	}

	@Operation(
			summary = "회원 탈퇴",
			description = """
					현재 로그인한 사용자의 계정을 비활성화한다. **Access Token 필요.**
					""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "탈퇴 성공 (data: null)"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "비밀번호 누락 (code: INVALID_INPUT_VALUE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "비밀번호 불일치(code: INVALID_CREDENTIALS) 또는 Access Token 오류(UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "403",
					description = "이미 탈퇴한 회원 (code: USER_DELETED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@DeleteMapping("/me")
	public ApiResponse<Void> withdraw(
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Valid @RequestBody WithdrawalRequest request,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId,
			@Parameter(hidden = true) HttpServletResponse response
	) {
		userService.withdraw(user.userId(), user.jti(), user.accessTokenExpiresAt(), request.password());
		response.addHeader(HttpHeaders.SET_COOKIE, expiredRefreshTokenCookie().toString());
		return ApiResponse.success(null, requestId);
	}

	private ResponseCookie expiredRefreshTokenCookie() {
		return ResponseCookie.from(REFRESH_TOKEN_COOKIE, "")
				.httpOnly(true)
				.secure(true)
				.sameSite("Lax")
				.path(REFRESH_TOKEN_COOKIE_PATH)
				.maxAge(0)
				.build();
	}
}

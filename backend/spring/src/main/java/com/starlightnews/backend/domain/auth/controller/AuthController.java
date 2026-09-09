package com.starlightnews.backend.domain.auth.controller;

import com.starlightnews.backend.domain.auth.dto.LoginIdAvailabilityResponse;
import com.starlightnews.backend.domain.auth.dto.LoginRequest;
import com.starlightnews.backend.domain.auth.dto.LoginResponse;
import com.starlightnews.backend.domain.auth.dto.LoginResult;
import com.starlightnews.backend.domain.auth.dto.RefreshResponse;
import com.starlightnews.backend.domain.auth.dto.RefreshResult;
import com.starlightnews.backend.domain.auth.dto.SignupRequest;
import com.starlightnews.backend.domain.auth.dto.SignupResponse;
import com.starlightnews.backend.domain.auth.service.AuthService;
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
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Pattern;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@Tag(name = "인증", description = "회원가입 · 로그인 · 토큰 재발급 · 로그아웃")
@RestController
@Validated
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/auth")
public class AuthController {

	private static final String LOGIN_ID_PATTERN = "^[a-z0-9_]{4,50}$";
	private static final String REFRESH_TOKEN_COOKIE = "refreshToken";
	private static final String REFRESH_TOKEN_COOKIE_PATH = ApiPaths.API_V1 + "/auth";

	private final AuthService authService;

	@Operation(
			summary = "로그인 아이디 중복 확인",
			description = """
					형식(영문 소문자·숫자·밑줄 4~50자)이 맞으면 DB에 같은 아이디가 있는지 확인한다.
					**이미 사용 중이어도 에러가 아니라 `available=false`** 로 응답한다. 인증 불필요.""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "아이디 형식 위반 (code: INVALID_INPUT_VALUE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@GetMapping("/login-id/availability")
	public ApiResponse<LoginIdAvailabilityResponse> checkLoginIdAvailability(
			@Parameter(description = "확인할 로그인 아이디", example = "starlight01", required = true)
			@RequestParam
			@Pattern(regexp = LOGIN_ID_PATTERN, message = "로그인 아이디는 영문 소문자·숫자·밑줄 조합 4~50자여야 합니다.")
			String loginId,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(authService.checkLoginIdAvailability(loginId), requestId);
	}

	@Operation(
			summary = "회원가입",
			description = """
					- `interestedTopicCodes` / `dislikedTopicCodes`: 생략하거나 빈 배열 가능
					- topic 코드: POLITICS, ECONOMY, SOCIETY, CULTURE, INTERNATIONAL, SPORTS, IT_SCIENCE""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "201", description = "가입 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "입력값 오류 — code: INVALID_INPUT_VALUE(형식) / INVALID_TOPIC / DUPLICATED_TOPIC / TOPIC_SELECTION_CONFLICT",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "409",
					description = "이미 사용 중인 로그인 아이디 (code: LOGIN_ID_ALREADY_EXISTS)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@PostMapping("/signup")
	@ResponseStatus(HttpStatus.CREATED)
	public ApiResponse<SignupResponse> signup(
			@Valid @RequestBody SignupRequest request,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(authService.signup(request), requestId);
	}

	@Operation(
			summary = "로그인",
			description = """
					Swagger에서 로그인 후 응답의 `accessToken` 을 복사해 우상단 **Authorize** 에 넣으면 보호 API를 호출할 수 있다.""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "로그인 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400",
					description = "loginId/password 누락 (code: INVALID_INPUT_VALUE)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "아이디 미존재 또는 비밀번호 불일치 (code: INVALID_CREDENTIALS)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "403",
					description = "탈퇴한 회원 (code: USER_DELETED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@PostMapping("/login")
	public ApiResponse<LoginResponse> login(
			@Valid @RequestBody LoginRequest request,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId,
			@Parameter(hidden = true) HttpServletResponse response
	) {
		LoginResult result = authService.login(request);
		response.addHeader(HttpHeaders.SET_COOKIE,
				refreshTokenCookie(result.refreshToken(), result.refreshTokenMaxAgeSeconds()).toString());
		return ApiResponse.success(result.response(), requestId);
	}

	@Operation(
			summary = "토큰 재발급",
			description = """
					- **동시에 두 번 이상 호출하지 말 것** (중복 시 세션이 무효화되어 재로그인 필요)
					Swagger에서는 로그인 시 저장된 쿠키가 자동으로 전송된다.""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "재발급 성공"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "code: INVALID_REFRESH_TOKEN(쿠키 없음/서명 오류) / EXPIRED_REFRESH_TOKEN / REFRESH_SESSION_NOT_FOUND(세션 없음·재사용)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "403",
					description = "탈퇴한 회원 (code: USER_DELETED)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@SecurityRequirements
	@PostMapping("/refresh")
	public ApiResponse<RefreshResponse> refresh(
			@Parameter(hidden = true)
			@CookieValue(name = REFRESH_TOKEN_COOKIE, required = false) String refreshToken,
			@Parameter(hidden = true) @RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId,
			@Parameter(hidden = true) HttpServletResponse response
	) {
		RefreshResult result = authService.refresh(refreshToken);
		response.addHeader(HttpHeaders.SET_COOKIE,
				refreshTokenCookie(result.refreshToken(), result.refreshTokenMaxAgeSeconds()).toString());
		return ApiResponse.success(result.response(), requestId);
	}

	@Operation(
			summary = "로그아웃",
			description = """
					**Access Token 필요** (우상단 Authorize 에 로그인 때 받은 accessToken 을 넣어야 한다).
					- 성공 시 **204 No Content** (응답 본문 없음)""")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "204", description = "로그아웃 성공 (본문 없음)"),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
					description = "Access Token 이 없거나 유효하지 않음 (code: UNAUTHORIZED / INVALID_ACCESS_TOKEN / EXPIRED_ACCESS_TOKEN)",
					content = @Content(schema = @Schema(implementation = ErrorResponse.class)))
	})
	@PostMapping("/logout")
	public ResponseEntity<Void> logout(
			@Parameter(hidden = true) @AuthenticationPrincipal AuthenticatedUser user,
			@Parameter(hidden = true)
			@CookieValue(name = REFRESH_TOKEN_COOKIE, required = false) String refreshToken
	) {
		authService.logout(user.jti(), user.accessTokenExpiresAt(), refreshToken);
		return ResponseEntity.noContent()
				.header(HttpHeaders.SET_COOKIE, refreshTokenCookie("", 0).toString())
				.build();
	}

	private ResponseCookie refreshTokenCookie(String value, long maxAgeSeconds) {
		return ResponseCookie.from(REFRESH_TOKEN_COOKIE, value)
				.httpOnly(true)
				.secure(true)
				.sameSite("Lax")
				.path(REFRESH_TOKEN_COOKIE_PATH)
				.maxAge(maxAgeSeconds)
				.build();
	}
}

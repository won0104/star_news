package com.starlightnews.backend.domain.auth.controller;

import com.starlightnews.backend.domain.auth.dto.LoginIdAvailabilityResponse;
import com.starlightnews.backend.domain.auth.dto.SignupRequest;
import com.starlightnews.backend.domain.auth.dto.SignupResponse;
import com.starlightnews.backend.domain.auth.service.AuthService;
import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.response.ApiResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Pattern;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
@RequiredArgsConstructor
@RequestMapping(ApiPaths.API_V1 + "/auth")
public class AuthController {

	private static final String LOGIN_ID_PATTERN = "^[a-z0-9_]{4,50}$";

	private final AuthService authService;

	@GetMapping("/login-id/availability")
	public ApiResponse<LoginIdAvailabilityResponse> checkLoginIdAvailability(
			@RequestParam
			@Pattern(regexp = LOGIN_ID_PATTERN, message = "로그인 아이디는 영문 소문자·숫자·밑줄 조합 4~50자여야 합니다.")
			String loginId,
			@RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(authService.checkLoginIdAvailability(loginId), requestId);
	}

	@PostMapping("/signup")
	@ResponseStatus(HttpStatus.CREATED)
	public ApiResponse<SignupResponse> signup(
			@Valid @RequestBody SignupRequest request,
			@RequestAttribute(RequestIdFilter.ATTRIBUTE_NAME) String requestId
	) {
		return ApiResponse.success(authService.signup(request), requestId);
	}
}

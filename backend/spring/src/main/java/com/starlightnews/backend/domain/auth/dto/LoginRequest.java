package com.starlightnews.backend.domain.auth.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * 로그인 요청. 형식 위반은 INVALID_INPUT_VALUE + errors[] 로 응답한다.
 * loginId/password 자체의 유효성은 사용자 조회·비밀번호 비교 결과로 판단하므로 NotBlank 만 검증한다.
 */
public record LoginRequest(

		@NotBlank(message = "로그인 아이디는 필수입니다.")
		String loginId,

		@NotBlank(message = "비밀번호는 필수입니다.")
		String password
) {
}

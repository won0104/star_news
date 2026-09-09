package com.starlightnews.backend.domain.user.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/**
 * 회원 탈퇴 요청. 민감한 작업이므로 현재 비밀번호를 다시 확인한다.
 * 비밀번호 누락은 INVALID_INPUT_VALUE + errors[] 로, 불일치는 INVALID_CREDENTIALS 로 응답한다.
 */
public record WithdrawalRequest(

		@Schema(description = "현재 비밀번호", example = "password1234")
		@NotBlank(message = "비밀번호는 필수입니다.")
		String password
) {
}

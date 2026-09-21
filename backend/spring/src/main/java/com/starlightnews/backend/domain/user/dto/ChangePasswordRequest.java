package com.starlightnews.backend.domain.user.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** 현재 비밀번호를 확인하고 새 비밀번호로 변경하는 요청. */
public record ChangePasswordRequest(
		@Schema(description = "현재 비밀번호", example = "password1234")
		@NotBlank(message = "현재 비밀번호는 필수입니다.")
		String currentPassword,

		@Schema(description = "새 비밀번호 (8~20자)", example = "newPassword1234")
		@NotBlank(message = "새 비밀번호는 필수입니다.")
		@Size(min = 8, max = 20, message = "새 비밀번호는 8~20자여야 합니다.")
		String newPassword
) {
}

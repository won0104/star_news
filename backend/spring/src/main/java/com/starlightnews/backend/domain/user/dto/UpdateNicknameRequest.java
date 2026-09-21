package com.starlightnews.backend.domain.user.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UpdateNicknameRequest(
		@Schema(description = "새 닉네임 (2~50자)", example = "새로운닉네임")
		@NotBlank(message = "닉네임은 필수입니다.")
		@Size(min = 2, max = 50, message = "닉네임은 2~50자여야 합니다.")
		String nickname
) {
}

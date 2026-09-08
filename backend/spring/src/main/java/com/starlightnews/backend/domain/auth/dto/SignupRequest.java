package com.starlightnews.backend.domain.auth.dto;

import java.util.List;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * 회원가입 요청.
 * 형식 검증(형식/길이)은 Bean Validation 으로 처리하고, 위반은 INVALID_INPUT_VALUE + errors[] 로 응답한다.
 * topic 코드의 유효성·중복·충돌 검증은 서비스에서 처리하므로 여기서는 String 으로 받는다.
 */
public record SignupRequest(

		@NotBlank(message = "로그인 아이디는 필수입니다.")
		@Pattern(
				regexp = "^[a-z0-9_]{4,50}$",
				message = "로그인 아이디는 영문 소문자·숫자·밑줄 조합 4~50자여야 합니다."
		)
		String loginId,

		@NotBlank(message = "비밀번호는 필수입니다.")
		@Size(min = 8, max = 20, message = "비밀번호는 8~20자여야 합니다.")
		String password,

		@NotBlank(message = "닉네임은 필수입니다.")
		@Size(min = 2, max = 50, message = "닉네임은 2~50자여야 합니다.")
		String nickname,

		List<String> interestedTopicCodes,

		List<String> dislikedTopicCodes
) {

	public SignupRequest {
		interestedTopicCodes = interestedTopicCodes == null ? List.of() : List.copyOf(interestedTopicCodes);
		dislikedTopicCodes = dislikedTopicCodes == null ? List.of() : List.copyOf(dislikedTopicCodes);
	}
}

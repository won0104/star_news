package com.starlightnews.backend.domain.auth.dto;

import java.util.List;

import com.starlightnews.backend.global.enums.TopicCode;

/**
 * 회원가입 응답. 로그인 토큰은 발급하지 않는다.
 * 선택한 topic 이 없으면 두 배열은 빈 배열로 반환한다.
 */
public record SignupResponse(
		Long userId,
		String loginId,
		String nickname,
		List<TopicCode> interestedTopicCodes,
		List<TopicCode> dislikedTopicCodes
) {

	public SignupResponse {
		interestedTopicCodes = interestedTopicCodes == null ? List.of() : List.copyOf(interestedTopicCodes);
		dislikedTopicCodes = dislikedTopicCodes == null ? List.of() : List.copyOf(dislikedTopicCodes);
	}
}

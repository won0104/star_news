package com.starlightnews.backend.domain.user.dto;

import java.util.List;

import com.starlightnews.backend.global.enums.TopicCode;

/** 현재 로그인한 사용자의 기본 정보와 관심·비관심 Topic 설정. */
public record UserProfileResponse(
		Long userId,
		String loginId,
		String nickname,
		List<TopicCode> interestedTopicCodes,
		List<TopicCode> dislikedTopicCodes
) {

	public UserProfileResponse {
		interestedTopicCodes = interestedTopicCodes == null ? List.of() : List.copyOf(interestedTopicCodes);
		dislikedTopicCodes = dislikedTopicCodes == null ? List.of() : List.copyOf(dislikedTopicCodes);
	}
}

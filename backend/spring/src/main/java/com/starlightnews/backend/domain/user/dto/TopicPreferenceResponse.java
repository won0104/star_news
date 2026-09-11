package com.starlightnews.backend.domain.user.dto;

import java.util.List;

import com.starlightnews.backend.global.enums.TopicCode;

/**
 * 사용자가 설정한 관심 또는 비관심 Topic 목록 응답.
 * 설정된 Topic이 없으면 빈 배열을 반환한다.
 */
public record TopicPreferenceResponse(
		List<TopicCode> topicCodes
) {

	public TopicPreferenceResponse {
		topicCodes = topicCodes == null ? List.of() : List.copyOf(topicCodes);
	}
}

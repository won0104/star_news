package com.starlightnews.backend.domain.user.dto;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;

/**
 * 관심 또는 비관심 Topic 목록을 최종 상태로 교체하는 요청.
 * Topic 코드의 유효성과 중복 여부는 서비스에서 검증한다.
 */
public record UpdateTopicPreferenceRequest(

		@Schema(
				description = "최종 Topic 목록. 빈 배열을 보내면 해당 유형을 모두 해제한다.",
				example = "[\"POLITICS\", \"ECONOMY\", \"IT_SCIENCE\"]"
		)
		@NotNull(message = "Topic 목록은 필수입니다.")
		List<String> topicCodes
) {

	public UpdateTopicPreferenceRequest {
		// null 항목은 서비스에서 INVALID_TOPIC으로 처리할 수 있도록 유지한다.
		topicCodes = topicCodes == null ? null : Collections.unmodifiableList(new ArrayList<>(topicCodes));
	}
}

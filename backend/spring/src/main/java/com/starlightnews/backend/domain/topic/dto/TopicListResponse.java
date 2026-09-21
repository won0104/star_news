package com.starlightnews.backend.domain.topic.dto;

import java.util.Arrays;
import java.util.List;

import com.starlightnews.backend.global.enums.TopicCode;

public record TopicListResponse(List<TopicItem> topics) {

	public static TopicListResponse all() {
		return new TopicListResponse(Arrays.stream(TopicCode.values())
				.map(topic -> new TopicItem(topic.name(), topic.labelKo()))
				.toList());
	}

	public record TopicItem(String code, String labelKo) {
	}
}

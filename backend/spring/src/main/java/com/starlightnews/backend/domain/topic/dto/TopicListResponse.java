package com.starlightnews.backend.domain.topic.dto;

import java.util.List;

/** 회원가입·사용자 설정에서 선택 가능한 전체 Topic 목록. */
public record TopicListResponse(List<TopicItem> topics) {

	public TopicListResponse {
		topics = topics == null ? List.of() : List.copyOf(topics);
	}

	public record TopicItem(String code, String labelKo) {
	}
}

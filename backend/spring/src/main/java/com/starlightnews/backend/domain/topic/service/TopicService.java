package com.starlightnews.backend.domain.topic.service;

import java.util.Arrays;

import com.starlightnews.backend.domain.topic.dto.TopicListResponse;
import com.starlightnews.backend.domain.topic.dto.TopicListResponse.TopicItem;
import com.starlightnews.backend.global.enums.TopicCode;
import org.springframework.stereotype.Service;

@Service
public class TopicService {

	public TopicListResponse getTopics() {
		return new TopicListResponse(Arrays.stream(TopicCode.values())
				.map(topic -> new TopicItem(topic.name(), topic.labelKo()))
				.toList());
	}
}

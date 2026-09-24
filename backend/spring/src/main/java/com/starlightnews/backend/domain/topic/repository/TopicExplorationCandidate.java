package com.starlightnews.backend.domain.topic.repository;

import com.starlightnews.backend.global.enums.TopicCode;

/**
 * Neo4j에서 Topic·Story 중복 제거와 순위 정렬을 마친 탐색 진입 Event 후보.
 */
public record TopicExplorationCandidate(
		TopicCode topicCode,
		String nodeId,
		String nodeTitle,
		long articleCount
) {
}

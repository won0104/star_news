package com.starlightnews.backend.domain.topic.repository;

import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.List;

import com.starlightnews.backend.global.enums.TopicCode;

/**
 * 최근 기사와 대표 Event 관계를 Topic별로 집계하는 Neo4j 읽기 전용 저장소.
 */
public interface TopicExplorationAggregationRepository {

	/**
	 * 지정 구간의 대표 Event를 Topic별로 조회한다.
	 * 각 Article의 primary Event만 집계하며, 같은 Topic·Story에서는 Event 하나만 반환한다.
	 * 반환 목록은 Topic 코드, 기사 수, 최신 기사 시각, Node ID 순으로 정렬되어 있다.
	 */
	List<TopicExplorationCandidate> findTopDistinctEventsByTopic(
			OffsetDateTime from,
			OffsetDateTime aggregationAt,
			Collection<TopicCode> topicCodes,
			int limitPerTopic
	);
}

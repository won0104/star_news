package com.starlightnews.backend.domain.trend.repository;

import java.time.OffsetDateTime;
import java.util.List;

/**
 * 최근 기사와 Event 관계를 집계하는 Neo4j 읽기 전용 저장소.
 */
public interface TrendAggregationRepository {

	/**
	 * 지정 구간의 대표 Event를 기사 수 내림차순으로 조회한다.
	 * 각 Article의 primary Event만 집계하며, 같은 Story에서는 Event 하나만 반환한다.
	 * 기사 수가 같으면 가장 최근 기사가 연결된 Event를 우선한다.
	 */
	List<TrendCandidate> findTopDistinctEvents(
			OffsetDateTime from,
			OffsetDateTime snapshotAt,
			int limit
	);
}

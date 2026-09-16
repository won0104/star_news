package com.starlightnews.backend.domain.recommendation.repository;

import java.util.List;

/**
 * 추천 Event 에 연결된 기사 조회. (Neo4j)
 */
public interface EventArticleRepository {

	/**
	 * Event 를 다루는 기사의 MySQL PK 를 관련도 높은 순으로 조회한다.
	 *
	 * <p>{@code (:Article)-[:COVERS {relevance}]->(:Event)} 의 relevance 를 쓴다. 같은 관련도면
	 * 최신 기사를 앞에 둔다. 관련도가 없는 관계도 있을 수 있어 없으면 0 으로 본다.
	 *
	 * @return 기사가 없거나 Event 가 없으면 빈 목록
	 */
	List<Long> findArticleIdsByEvent(String eventId);
}

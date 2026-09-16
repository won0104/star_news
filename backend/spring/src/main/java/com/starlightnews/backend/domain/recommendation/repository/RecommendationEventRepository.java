package com.starlightnews.backend.domain.recommendation.repository;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * 추천 Event 표시 정보 저장. ({@code recommendation_events})
 */
public interface RecommendationEventRepository extends JpaRepository<RecommendationEvent, String> {

	/**
	 * 제목과 Topic 을 최신으로 맞춘다. 없으면 새로 만든다.
	 *
	 * <p><b>요약은 건드리지 않는다.</b> 회차마다 덮어쓰면 매번 다시 만들어야 한다.
	 *
	 * <p>제목이 실제로 바뀐 경우에만 {@code event_updated_at} 을 갱신한다. 요약을 다시 만들지
	 * 판단하는 기준이라, 내용이 그대로인데 회차마다 찍으면 매번 재생성 대상이 된다.
	 * 대입은 왼쪽부터 평가되므로 제목을 덮어쓰기 전에 비교해야 한다.
	 */
	@Modifying
	@Query(value = """
			INSERT INTO recommendation_events (event_id, title, topic_code)
			VALUES (:eventId, :title, :topicCode) AS incoming
			ON DUPLICATE KEY UPDATE
			    event_updated_at = IF(recommendation_events.title <> incoming.title,
			                          NOW(6), recommendation_events.event_updated_at),
			    title = incoming.title,
			    topic_code = incoming.topic_code
			""", nativeQuery = true)
	void upsert(@Param("eventId") String eventId,
			@Param("title") String title,
			@Param("topicCode") String topicCode);
}

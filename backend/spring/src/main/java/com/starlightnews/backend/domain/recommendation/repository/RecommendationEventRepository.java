package com.starlightnews.backend.domain.recommendation.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;

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

	/**
	 * 요약을 만들어야 하는 Event 의 ID 를 찾는다.
	 *
	 * <p>두 경우다. 아직 요약이 없거나, 요약을 만든 뒤 Event 제목이 바뀐 경우.
	 * 앞의 조건이 지난 회차에 실패한 Event 도 함께 잡아, 다음 회차에 저절로 다시 시도된다.
	 *
	 * <p>이번 회차에 실제로 추천된 Event 만 본다. 쓰이지도 않을 Event 의 요약을 만들면 GMS 호출만
	 * 늘어난다.
	 */
	@Query("SELECT e.eventId FROM RecommendationEvent e "
			+ "WHERE e.eventId IN :eventIds "
			+ "AND (e.summary IS NULL "
			+ "     OR (e.eventUpdatedAt IS NOT NULL "
			+ "         AND (e.summaryGeneratedAt IS NULL OR e.eventUpdatedAt > e.summaryGeneratedAt)))")
	List<String> findEventIdsNeedingSummary(@Param("eventIds") Collection<String> eventIds);

	/** 요약 생성을 시작했다고 표시한다. 중간에 죽으면 이 상태가 남아 구분된다. */
	@Modifying
	@Query("UPDATE RecommendationEvent e SET e.summaryStatus = 'PROCESSING' WHERE e.eventId = :eventId")
	void markSummaryProcessing(@Param("eventId") String eventId);

	/** 만들어진 요약을 저장한다. */
	@Modifying
	@Query("UPDATE RecommendationEvent e SET e.summary = :summary, e.summaryStatus = 'COMPLETED', "
			+ "e.summaryGeneratedAt = :generatedAt WHERE e.eventId = :eventId")
	void saveSummary(@Param("eventId") String eventId,
			@Param("summary") String summary,
			@Param("generatedAt") LocalDateTime generatedAt);

	/**
	 * 요약 생성에 실패했다고 표시한다.
	 *
	 * <p>{@code summary} 는 건드리지 않는다. 지난 회차에 만들어 둔 요약이 있으면 그대로 보여 주는
	 * 편이 빈 화면보다 낫다.
	 */
	@Modifying
	@Query("UPDATE RecommendationEvent e SET e.summaryStatus = 'FAILED' WHERE e.eventId = :eventId")
	void markSummaryFailed(@Param("eventId") String eventId);
}

package com.starlightnews.backend.domain.recommendation.domain;

import java.time.LocalDateTime;

import com.starlightnews.backend.global.enums.TopicCode;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * 추천에 쓰이는 Event 의 표시 정보와 요약 캐시. ({@code recommendation_events})

 * <p>요약({@code summary})은 이 배치가 만들지 않는다. 별도 단계가 채우고 {@code summaryStatus} 로
 * 상태를 관리하므로, 회차를 저장할 때 덮어쓰지 않도록 주의한다.
 */
@Entity
@Table(name = "recommendation_events")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class RecommendationEvent {

	/** Neo4j Event 의 nodeId. recommendation_events.event_id 는 CHAR(36) 이다. */
	@Id
	@JdbcTypeCode(SqlTypes.CHAR)
	@Column(name = "event_id", length = 36)
	private String eventId;

	@Column(name = "title", nullable = false, length = 500)
	private String title;

	@Column(name = "summary")
	private String summary;

	@Column(name = "summary_status", nullable = false, length = 32)
	private String summaryStatus;

	@Enumerated(EnumType.STRING)
	@Column(name = "topic_code", nullable = false, length = 32)
	private TopicCode topicCode;

	/** Event 내용이 바뀐 시각. 요약을 다시 만들어야 하는지 판단하는 기준이다. */
	@Column(name = "event_updated_at")
	private LocalDateTime eventUpdatedAt;

	@Column(name = "summary_generated_at")
	private LocalDateTime summaryGeneratedAt;

	@Column(name = "created_at", insertable = false, updatable = false)
	private LocalDateTime createdAt;

	@Column(name = "updated_at", insertable = false, updatable = false)
	private LocalDateTime updatedAt;
}

package com.starlightnews.backend.domain.recommendation.domain;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import com.starlightnews.backend.global.enums.RecommendationCycle;
import com.starlightnews.backend.global.enums.RecommendationType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * 사용자별 회차 추천 결과 한 건. ({@code user_recommendations})
 *
 * <p>한 회차 안에서 {@code (userId, availableAt, recommendationType)} 기준으로 {@code eventId} 와
 * {@code rank} 가 각각 유일하다. 같은 순위를 두 번 넣으면 저장이 실패한다.
 *
 * <p>{@code reason} 컬럼은 매핑하지 않는다. FastAPI 가 추천 이유를 더 이상 보내지 않아 늘 비어 있다.
 *
 * <p>{@code availableAt} 이 공개 시각이다. 조회 API 가 {@code availableAt <= now} 중 가장 최근
 * 회차를 보여주므로, 이 값이 틀리면 추천이 일찍 노출되거나 영영 보이지 않는다.
 */
@Entity
@Table(name = "user_recommendations")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserRecommendation {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "user_recommendation_id")
	private Long userRecommendationId;

	@Column(name = "user_id", nullable = false)
	private Long userId;

	/** Neo4j Event 의 nodeId. user_recommendations.event_id 는 CHAR(36) 이다. */
	@JdbcTypeCode(SqlTypes.CHAR)
	@Column(name = "event_id", nullable = false, length = 36)
	private String eventId;

	@Enumerated(EnumType.STRING)
	@Column(name = "recommendation_type", nullable = false, length = 32)
	private RecommendationType recommendationType;

	@Column(name = "recommendation_score", nullable = false, precision = 10, scale = 6)
	private BigDecimal recommendationScore;

	/**
	 * 회차 안에서의 표시 순위.
	 *
	 * <p>{@code rank} 는 MySQL 8 예약어라 인용 부호를 붙인다. 컬럼이 TINYINT UNSIGNED 라
	 * Short 기본 매핑(SMALLINT)과 어긋나므로 JDBC 타입을 지정한다.
	 */
	@JdbcTypeCode(SqlTypes.TINYINT)
	@Column(name = "`rank`", nullable = false)
	private Short rank;

	/** 추천을 계산한 시각. 05:30 · 17:30 */
	@Column(name = "recommended_at", nullable = false)
	private LocalDateTime recommendedAt;

	@Enumerated(EnumType.STRING)
	@Column(name = "cycle", nullable = false, length = 8)
	private RecommendationCycle cycle;

	/** 사용자에게 공개되는 시각. 06:00 · 18:00 */
	@Column(name = "available_at", nullable = false)
	private LocalDateTime availableAt;

	public UserRecommendation(Long userId, String eventId, RecommendationType recommendationType,
			BigDecimal recommendationScore, Short rank,
			LocalDateTime recommendedAt, RecommendationCycle cycle, LocalDateTime availableAt) {
		this.userId = userId;
		this.eventId = eventId;
		this.recommendationType = recommendationType;
		this.recommendationScore = recommendationScore;
		this.rank = rank;
		this.recommendedAt = recommendedAt;
		this.cycle = cycle;
		this.availableAt = availableAt;
	}
}

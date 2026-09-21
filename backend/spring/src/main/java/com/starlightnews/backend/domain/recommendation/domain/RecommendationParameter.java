package com.starlightnews.backend.domain.recommendation.domain;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 재튜닝으로 정해진 추천 가중치 한 벌. ({@code recommendation_parameters})
 *
 * <p>주 1회 FastAPI 가 계산한 값을 그대로 받아 쌓는다. 추천 회차는 가장 최근 행을 읽어 쓰고,
 * 지난 행은 주차별 비교를 위해 남긴다.
 */
@Entity
@Table(name = "recommendation_parameters")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class RecommendationParameter {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "parameter_id")
	private Long parameterId;

	@Column(name = "cbf_weight", nullable = false, precision = 5, scale = 4)
	private BigDecimal cbfWeight;

	@Column(name = "cf_weight", nullable = false, precision = 5, scale = 4)
	private BigDecimal cfWeight;

	/** 평가 지표. 참고용이라 추천 계산에는 쓰지 않는다. */
	@Column(name = "ndcg_at10", precision = 6, scale = 4)
	private BigDecimal ndcgAt10;

	@Column(name = "hit_rate_at10", precision = 6, scale = 4)
	private BigDecimal hitRateAt10;

	@Column(name = "recall_at10", precision = 6, scale = 4)
	private BigDecimal recallAt10;

	@Column(name = "computed_at", nullable = false)
	private LocalDateTime computedAt;

	public RecommendationParameter(BigDecimal cbfWeight, BigDecimal cfWeight, BigDecimal ndcgAt10,
			BigDecimal hitRateAt10, BigDecimal recallAt10, LocalDateTime computedAt) {
		this.cbfWeight = cbfWeight;
		this.cfWeight = cfWeight;
		this.ndcgAt10 = ndcgAt10;
		this.hitRateAt10 = hitRateAt10;
		this.recallAt10 = recallAt10;
		this.computedAt = computedAt;
	}

	public RecommendationWeights weights() {
		return new RecommendationWeights(cbfWeight, cfWeight);
	}
}

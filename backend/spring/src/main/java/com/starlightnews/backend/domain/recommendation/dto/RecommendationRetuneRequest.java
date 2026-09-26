package com.starlightnews.backend.domain.recommendation.dto;

import java.math.BigDecimal;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationWeights;

/**
 * {@code POST /internal/v1/recommendations/retune} 요청 본문.
 *
 * <p>지금 실제로 적용 중인 가중치를 실어 보낸다.
 */
public record RecommendationRetuneRequest(BigDecimal currentCbfWeight, BigDecimal currentCfWeight) {

	public static RecommendationRetuneRequest from(RecommendationWeights current) {
		return new RecommendationRetuneRequest(current.cbf(), current.cf());
	}
}

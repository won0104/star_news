package com.starlightnews.backend.domain.recommendation.dto;

import java.math.BigDecimal;

/**
 * {@code POST /internal/v1/recommendations/retune} 응답 본문.
 *
 * <p>FastAPI 가 그리드서치로 고른 가중치와 그때 잰 평가 지표가 온다. 지표는 참고용이라 비어 있을
 * 수 있다.
 */
public record RecommendationRetuneResponse(Data data) {

	public record Data(
			BigDecimal cbfWeight,
			BigDecimal cfWeight,
			BigDecimal ndcgAt10,
			BigDecimal hitRateAt10,
			BigDecimal recallAt10
	) {
	}
}

package com.starlightnews.backend.domain.recommendation.service;

import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse;
import com.starlightnews.backend.global.client.InternalApiErrorCode;

/**
 * 묶음 하나의 추천 계산 결과.
 *
 * <p>실패 원인을 함께 돌려준다. 회차 실행 기록에 남겨 두어야 나중에 왜 추천이 비었는지 알 수 있다.
 */
public sealed interface RecommendationCalculateOutcome {

	record Calculated(RecommendationCalculateResponse response) implements RecommendationCalculateOutcome {
	}

	record Failed(InternalApiErrorCode errorCode) implements RecommendationCalculateOutcome {
	}
}

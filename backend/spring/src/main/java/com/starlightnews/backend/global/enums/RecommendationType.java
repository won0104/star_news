package com.starlightnews.backend.global.enums;

import java.util.Arrays;
import java.util.Optional;

/**
 * 추천이 만들어진 근거 유형. ({@code user_recommendations.recommendation_type})
 *
 * <p>FastAPI 가 계산 결과에 실어 보내는 값을 그대로 저장한다.
 */
public enum RecommendationType {

	/** 사용자의 관심·소비 이력과 비슷한 Event. */
	INTEREST_BASED,

	/** 탐색 중인 Story 에서 아직 접하지 않은 Event. */
	KNOWLEDGE_GAP;

	/** 모르는 값이면 비어 있는 결과를 돌려준다. FastAPI 가 새 유형을 추가해도 저장이 통째로 깨지지 않게 한다. */
	public static Optional<RecommendationType> from(String value) {
		return Arrays.stream(values())
				.filter(type -> type.name().equalsIgnoreCase(value))
				.findFirst();
	}
}

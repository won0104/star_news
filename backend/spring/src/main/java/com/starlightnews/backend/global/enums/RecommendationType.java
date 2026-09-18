package com.starlightnews.backend.global.enums;

import java.util.Arrays;
import java.util.Optional;

/**
 * 추천을 어떻게 계산했는지. ({@code user_recommendations.recommendation_type})
 *
 * <p>FastAPI 가 계산 결과에 실어 보내는 값을 그대로 저장한다. 한 사용자의 한 회차는 한 가지 유형만
 * 갖는다. 소비 이력이 있으면 정상 계산, 없으면 콜드스타트로 판정하기 때문이다.
 */
public enum RecommendationType {

	/** 관심·소비 이력을 바탕으로 내용 기반과 협업 필터링을 결합해 계산했다. */
	NORMAL,

	/** 소비 이력이 없어 최신·인기 Event 로 대신했다. */
	COLD_START;

	/** 모르는 값이면 비어 있는 결과를 돌려준다. FastAPI 가 새 유형을 추가해도 저장이 통째로 깨지지 않게 한다. */
	public static Optional<RecommendationType> from(String value) {
		return Arrays.stream(values())
				.filter(type -> type.name().equalsIgnoreCase(value))
				.findFirst();
	}
}

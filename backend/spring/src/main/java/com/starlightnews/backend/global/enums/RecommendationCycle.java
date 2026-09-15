package com.starlightnews.backend.global.enums;

/**
 * 추천 회차. ({@code user_recommendations.cycle})
 *
 * <p>추천은 실시간으로 계산하지 않고 하루 두 번 미리 만들어 둔다. 계산은 05:30·17:30 에 하고
 * 공개는 06:00·18:00 이다. 이 값이 오전·오후 결과를 가른다.
 */
public enum RecommendationCycle {

	/** 오전 회차. 06:00 KST 공개. */
	AM,

	/** 오후 회차. 18:00 KST 공개. */
	PM
}

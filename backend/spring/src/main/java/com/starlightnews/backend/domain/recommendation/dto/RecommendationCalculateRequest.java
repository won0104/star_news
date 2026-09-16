package com.starlightnews.backend.domain.recommendation.dto;

import java.util.List;

import com.starlightnews.backend.global.enums.RecommendationCycle;

/**
 * {@code POST /internal/v1/recommendations/calculate} 요청 본문.
 *
 * <p>사용자별로 따로 호출하지 않고 여러 명을 한 요청에 묶어 보낸다.
 *
 * @param cycle 이 회차가 오전인지 오후인지. 응답에도 같은 값이 실려 온다
 */
public record RecommendationCalculateRequest(
		RecommendationCycle cycle,
		List<UserRequest> users
) {

	/**
	 * 추천을 계산할 사용자 하나.
	 *
	 * @param limit 이 사용자에게 돌려줄 추천 Event 최대 개수
	 */
	public record UserRequest(Long userId, int limit) {
	}

	/** 사용자 ID 목록으로 요청을 만든다. */
	public static RecommendationCalculateRequest of(List<Long> userIds, RecommendationCycle cycle, int limit) {
		return new RecommendationCalculateRequest(cycle,
				userIds.stream().map(userId -> new UserRequest(userId, limit)).toList());
	}
}

package com.starlightnews.backend.domain.recommendation.domain;

import java.util.EnumSet;
import java.util.Set;

/**
 * 추천 생성 회차의 실행 상태.
 */
public enum RecommendationRunStatus {

	/** 돌고 있다. 서버가 도중에 내려가면 이 상태로 남는다. */
	RUNNING,

	/** 모든 묶음이 저장까지 끝났다. 대상 사용자가 없던 회차도 여기에 든다. */
	COMPLETED,

	/** 일부 묶음만 실패했다. 나머지 사용자의 추천은 저장돼 있다. */
	PARTIAL,

	/** 성공한 묶음이 하나도 없거나 회차가 도중에 예외로 끊겼다. */
	FAILED;

	/**
	 * 사용자에게 보여 줄 수 있는 상태.
	 *
	 * <p>{@link #PARTIAL} 도 보여 준다. 실패한 묶음의 사용자는 이 회차 추천이 저장돼 있지 않아 직전
	 * 회차를 보게 되고, 나머지 사용자는 새 추천을 본다. 막으면 일부 실패 때문에 모두가 12시간 전
	 * 추천을 본다.
	 */
	public static Set<RecommendationRunStatus> visible() {
		return EnumSet.of(COMPLETED, PARTIAL);
	}

	/** 묶음 결과로 끝난 회차의 상태를 정한다. */
	public static RecommendationRunStatus of(int totalChunks, int failedChunks) {
		if (failedChunks == 0) {
			return COMPLETED;
		}
		return failedChunks < totalChunks ? PARTIAL : FAILED;
	}
}

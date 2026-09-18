package com.starlightnews.backend.domain.recommendation.domain;

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

	/** 묶음 결과로 끝난 회차의 상태를 정한다. */
	public static RecommendationRunStatus of(int totalChunks, int failedChunks) {
		if (failedChunks == 0) {
			return COMPLETED;
		}
		return failedChunks < totalChunks ? PARTIAL : FAILED;
	}
}

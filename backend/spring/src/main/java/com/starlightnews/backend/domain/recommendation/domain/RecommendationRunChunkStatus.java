package com.starlightnews.backend.domain.recommendation.domain;

/**
 * 회차 안 사용자 묶음 하나의 결과.
 */
public enum RecommendationRunChunkStatus {

	/** 계산과 저장이 끝났다. 형식이 맞지 않아 건너뛴 추천이 있어도 성공이다. */
	SUCCEEDED,

	/** 계산 또는 저장이 실패해 이 묶음 사용자들은 이번 회차 추천이 없다. */
	FAILED
}

package com.starlightnews.backend.domain.recommendation.service;

/**
 * 회차 저장 결과.
 *
 * @param storedUsers  추천이 한 건이라도 저장된 사용자 수
 * @param storedItems  저장한 추천 건수
 * @param skippedItems 형식이 맞지 않아 건너뛴 추천 건수
 */
public record RecommendationStoreResult(int storedUsers, int storedItems, int skippedItems) {

	public static RecommendationStoreResult empty() {
		return new RecommendationStoreResult(0, 0, 0);
	}
}

package com.starlightnews.backend.domain.recommendation.service;

/**
 * 한 회차 추천 생성 결과.
 *
 * @param storedUsers  추천이 한 건이라도 저장된 사용자 수
 * @param storedItems  저장한 추천 건수
 * @param skippedItems 형식이 맞지 않아 건너뛴 추천 건수
 * @param failedUsers  계산 요청이 실패해 추천을 받지 못한 사용자 수
 */
public record RecommendationBatchResult(
		int storedUsers,
		int storedItems,
		int skippedItems,
		int failedUsers
) {

	public static RecommendationBatchResult empty() {
		return new RecommendationBatchResult(0, 0, 0, 0);
	}

	public RecommendationBatchResult plus(RecommendationStoreResult stored) {
		return new RecommendationBatchResult(
				storedUsers + stored.storedUsers(),
				storedItems + stored.storedItems(),
				skippedItems + stored.skippedItems(),
				failedUsers);
	}

	public RecommendationBatchResult plusFailed(int userCount) {
		return new RecommendationBatchResult(storedUsers, storedItems, skippedItems,
				failedUsers + userCount);
	}
}

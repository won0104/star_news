package com.starlightnews.backend.domain.recommendation.dto;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;

import com.starlightnews.backend.global.enums.RecommendationCycle;
import com.starlightnews.backend.global.enums.RecommendationType;
import com.starlightnews.backend.global.enums.TopicCode;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 추천 보드 조회 응답. 공개된 최신 회차 하나를 순위 순으로 담는다.
 */
public record RecommendationBoardResponse(

		@Schema(description = "회차 구분 (공개된 회차가 없으면 null)", example = "PM", nullable = true)
		RecommendationCycle cycle,

		@Schema(description = "추천을 계산한 시각 (05:30 · 17:30)", nullable = true,
				example = "2026-09-16T17:30:00+09:00")
		OffsetDateTime generatedAt,

		@Schema(description = "사용자에게 공개된 시각 (06:00 · 18:00)", nullable = true,
				example = "2026-09-16T18:00:00+09:00")
		OffsetDateTime availableAt,

		@Schema(description = "순위 순 추천 목록. 한 회차 전부를 담는다")
		List<Item> items
) {

	/** 공개된 회차가 없을 때의 응답. */
	public static RecommendationBoardResponse empty() {
		return new RecommendationBoardResponse(null, null, null, List.of());
	}

	@Schema(name = "RecommendationBoardItem")
	public record Item(

			@Schema(description = "추천 상세 조회 키. 카드 링크에는 eventId 가 아니라 이 값을 쓴다",
					example = "10241")
			long userRecommendationId,

			@Schema(description = "Neo4j Event 의 nodeId",
					example = "00000020-0920-4000-8000-000000000001")
			String eventId,

			@Schema(description = "Event 표시 이름", example = "한국은행 1월 기준금리 동결")
			String label,

			@Schema(description = "Event 의 Topic", example = "ECONOMY")
			TopicCode topicCode,

			@Schema(description = "추천 점수", example = "0.920000")
			BigDecimal score,

			@Schema(description = "회차 안에서의 표시 순위", example = "1")
			short rank,

			@Schema(description = "추천 계산 방식. NORMAL(이력 기반) 또는 COLD_START(이력이 없어 최신·인기 Event 로 대체)",
					example = "NORMAL")
			RecommendationType recommendationType
	) {
	}
}

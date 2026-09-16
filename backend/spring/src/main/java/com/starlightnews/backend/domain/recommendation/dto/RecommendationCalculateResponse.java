package com.starlightnews.backend.domain.recommendation.dto;

import java.math.BigDecimal;
import java.util.List;

/**
 * {@code POST /internal/v1/recommendations/calculate} 응답 본문.
 *
 * <p>FastAPI 는 결과를 {@code data} 로 한 겹 감싸서 돌려준다. 한 요청에 여러 사용자를 묶어 보내므로
 * 결과도 사용자별로 나뉘어 온다.
 */
public record RecommendationCalculateResponse(Data data) {

	public record Data(String cycle, List<UserResult> results) {

		public Data {
			results = results == null ? List.of() : List.copyOf(results);
		}
	}

	/** 사용자 한 명의 추천 목록. */
	public record UserResult(Long userId, List<Item> items) {

		public UserResult {
			items = items == null ? List.of() : List.copyOf(items);
		}
	}

	/**
	 * 추천 Event 한 건.
	 *
	 * @param label              Event 화면 표시 이름. {@code recommendation_events.title} 로 저장한다
	 * @param topicCode          Event 의 대표 Topic
	 * @param recommendationType {@code INTEREST_BASED} 또는 {@code KNOWLEDGE_GAP}
	 */
	public record Item(
			String eventId,
			String label,
			String topicCode,
			BigDecimal score,
			Short rank,
			String recommendationType,
			String reason
	) {
	}

	public List<UserResult> results() {
		return data == null ? List.of() : data.results();
	}

	/** FastAPI 가 답한 회차. 요청에 실어 보낸 값과 같아야 한다. */
	public String cycle() {
		return data == null ? null : data.cycle();
	}
}

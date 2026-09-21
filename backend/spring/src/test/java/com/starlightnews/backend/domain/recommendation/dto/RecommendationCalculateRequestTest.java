package com.starlightnews.backend.domain.recommendation.dto;

import java.util.List;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationWeights;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class RecommendationCalculateRequestTest {

	private static final RecommendationWeights WEIGHTS = RecommendationWeights.DEFAULT;

	private final ObjectMapper objectMapper = new ObjectMapper();

	@Test
	void 사용자_목록으로_요청을_만든다() {
		var request = RecommendationCalculateRequest.of(List.of(1L, 2L), RecommendationCycle.AM, 10, WEIGHTS);

		assertThat(request.cycle()).isEqualTo(RecommendationCycle.AM);
		assertThat(request.users())
				.extracting(RecommendationCalculateRequest.UserRequest::userId,
						RecommendationCalculateRequest.UserRequest::limit)
				.containsExactly(
						org.assertj.core.api.Assertions.tuple(1L, 10),
						org.assertj.core.api.Assertions.tuple(2L, 10));
	}

	@Test
	void 명세와_같은_모양으로_직렬화된다() throws Exception {
		// 이름이 하나라도 다르면 FastAPI 가 422 로 거절한다.
		var request = RecommendationCalculateRequest.of(List.of(1L), RecommendationCycle.AM, 10, WEIGHTS);

		JsonNode json = objectMapper.readTree(objectMapper.writeValueAsString(request));

		assertThat(json.fieldNames()).toIterable()
				.containsExactlyInAnyOrder("cycle", "users", "cbfWeight", "cfWeight");
		assertThat(json.get("cycle").asText()).isEqualTo("AM");
		assertThat(json.get("users").get(0).fieldNames()).toIterable()
				.containsExactlyInAnyOrder("userId", "limit");
		assertThat(json.get("users").get(0).get("userId").asLong()).isEqualTo(1L);
		assertThat(json.get("users").get(0).get("limit").asInt()).isEqualTo(10);
	}

	@Test
	void 오후_회차는_PM으로_나간다() {
		var request = RecommendationCalculateRequest.of(List.of(1L), RecommendationCycle.PM, 10, WEIGHTS);

		assertThat(request.cycle()).isEqualTo(RecommendationCycle.PM);
	}

	@Test
	void 사용자가_없으면_빈_목록이다() {
		assertThat(RecommendationCalculateRequest.of(List.of(), RecommendationCycle.AM, 10, WEIGHTS).users())
				.isEmpty();
	}

	@Test
	void 재튜닝으로_정해진_가중치를_함께_보낸다() {
		// FastAPI 가 이 값으로 CBF·CF 점수를 조합한다. 빠지면 추천이 기본 설정으로 계산된다.
		var weights = new RecommendationWeights(new java.math.BigDecimal("0.8000"),
				new java.math.BigDecimal("0.2000"));

		var request = RecommendationCalculateRequest.of(List.of(1L), RecommendationCycle.AM, 10, weights);

		assertThat(request.cbfWeight()).isEqualByComparingTo("0.8000");
		assertThat(request.cfWeight()).isEqualByComparingTo("0.2000");
	}
}

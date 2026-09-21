package com.starlightnews.backend.domain.recommendation.domain;

import java.math.BigDecimal;

/**
 * 추천 계산에 쓰는 가중치. FastAPI 요청에 실어 보낸다.
 *
 * @param cbf 콘텐츠 기반 점수 가중치
 * @param cf  협업 필터링 점수 가중치
 */
public record RecommendationWeights(BigDecimal cbf, BigDecimal cf) {

	/**
	 * 재튜닝 결과가 아직 없을 때 쓰는 값.
	 *
	 * <p>첫 주와 조회 실패가 같은 경로로 처리된다. 가중치가 없다고 추천 회차를 멈추면, 재튜닝
	 * 한 번 실패한 뒤 12시간마다 추천이 비게 된다.
	 */
	public static final RecommendationWeights DEFAULT =
			new RecommendationWeights(new BigDecimal("0.7000"), new BigDecimal("0.3000"));
}

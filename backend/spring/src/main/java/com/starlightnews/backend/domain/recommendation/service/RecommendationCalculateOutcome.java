package com.starlightnews.backend.domain.recommendation.service;

import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse;
import com.starlightnews.backend.global.client.InternalApiErrorCode;

/**
 * 묶음 하나의 추천 계산 결과.
 *
 * <p>실패 원인을 함께 돌려준다. 회차 실행 기록에 남겨 두어야 나중에 왜 추천이 비었는지 알 수 있다.
 */
public sealed interface RecommendationCalculateOutcome {

	record Calculated(RecommendationCalculateResponse response) implements RecommendationCalculateOutcome {
	}

	record Failed(InternalApiErrorCode errorCode) implements RecommendationCalculateOutcome {

		/**
		 * 같은 회차 안에서 다시 보낼 만한 실패인지.
		 *
		 * <p>FastAPI 나 Neo4j 가 잠깐 막힌 경우만 해당한다. 인증·요청 형식 오류는 설정이나 코드를
		 * 고쳐야 풀리고, User Graph 가 없는 404 는 다음 동기화가 돌아야 풀린다. 이런 실패를 다시
		 * 보내면 공개 시각까지 남은 시간만 쓴다.
		 */
		public boolean retryable() {
			return errorCode == InternalApiErrorCode.INTERNAL_API_UNAVAILABLE
					|| errorCode == InternalApiErrorCode.INTERNAL_API_TIMEOUT
					|| errorCode == InternalApiErrorCode.INTERNAL_API_FAILED;
		}
	}
}

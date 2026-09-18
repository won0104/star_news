package com.starlightnews.backend.domain.recommendation.service;

import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateRequest;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse;
import com.starlightnews.backend.domain.recommendation.service.RecommendationCalculateOutcome.Calculated;
import com.starlightnews.backend.domain.recommendation.service.RecommendationCalculateOutcome.Failed;
import com.starlightnews.backend.global.client.FastApiClient;
import com.starlightnews.backend.global.client.InternalApiErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 사용자 묶음의 추천 계산을 FastAPI 에 요청한다.
 *
 * <p>묶음 하나가 실패해도 예외를 올리지 않는다. 회차 전체를 무너뜨리는 대신 나머지 묶음을 계속
 * 보내기 위해서다. 사용자 그래프 동기화와 같은 방식이다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationCalculateClient {

	private static final String CALCULATE_PATH = "/internal/v1/recommendations/calculate";

	private final FastApiClient fastApiClient;

	/**
	 * 묶음 하나의 추천을 계산한다.
	 *
	 * @return 계산 결과. 실패하면 원인을 담는다
	 */
	public RecommendationCalculateOutcome calculate(RecommendationCalculateRequest request) {
		if (request.users().isEmpty()) {
			// 보낼 사람이 없으면 할 일도 없다. 실패로 세면 빈 묶음이 회차를 PARTIAL 로 만든다.
			return new Calculated(new RecommendationCalculateResponse(null));
		}

		try {
			return new Calculated(fastApiClient.post(CALCULATE_PATH, request,
					RecommendationCalculateResponse.class));
		} catch (BusinessException failure) {
			InternalApiErrorCode errorCode = toInternalErrorCode(failure);
			logFailure(errorCode, request.users().size());
			return new Failed(errorCode);
		}
	}

	/** FastApiClient 는 내부 API 오류 코드만 던진다. 혹시 다른 코드가 오면 원인 불명 실패로 본다. */
	private InternalApiErrorCode toInternalErrorCode(BusinessException failure) {
		return failure.getErrorCode() instanceof InternalApiErrorCode code
				? code : InternalApiErrorCode.INTERNAL_API_FAILED;
	}

	private void logFailure(InternalApiErrorCode errorCode, int userCount) {
		if (errorCode == InternalApiErrorCode.INTERNAL_API_NOT_FOUND) {
			// User Graph 가 아직 없는 사용자가 섞여 있다. 신규 가입자가 대표적이다.
			// 다시 시도해도 같은 결과이고, 05:00·17:00 동기화가 먼저 돌아야 풀린다.
			log.warn("User Graph 가 없어 추천을 계산하지 못했습니다. (사용자 {}명)", userCount);
			return;
		}

		log.warn("추천 계산 실패 (사용자 {}명, 원인={})", userCount, errorCode.getCode());
	}
}

package com.starlightnews.backend.domain.recommendation.service;

import java.util.Optional;

import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateRequest;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse;
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
	 * @return 계산 결과. 실패하면 비어 있다
	 */
	public Optional<RecommendationCalculateResponse> calculate(RecommendationCalculateRequest request) {
		if (request.users().isEmpty()) {
			return Optional.empty();
		}

		try {
			return Optional.of(fastApiClient.post(CALCULATE_PATH, request,
					RecommendationCalculateResponse.class));
		} catch (BusinessException failure) {
			logFailure(failure, request.users().size());
			return Optional.empty();
		}
	}

	private void logFailure(BusinessException failure, int userCount) {
		if (failure.getErrorCode() == InternalApiErrorCode.INTERNAL_API_NOT_FOUND) {
			// User Graph 가 아직 없는 사용자가 섞여 있다. 신규 가입자가 대표적이다.
			// 다시 시도해도 같은 결과이고, 05:00·17:00 동기화가 먼저 돌아야 풀린다.
			log.warn("User Graph 가 없어 추천을 계산하지 못했습니다. (사용자 {}명)", userCount);
			return;
		}

		log.warn("추천 계산 실패 (사용자 {}명, 원인={})", userCount, failure.getErrorCode().getCode());
	}
}

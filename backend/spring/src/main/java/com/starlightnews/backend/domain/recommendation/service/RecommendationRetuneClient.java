package com.starlightnews.backend.domain.recommendation.service;

import java.util.Optional;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationWeights;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationRetuneRequest;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationRetuneResponse;
import com.starlightnews.backend.global.client.FastApiClient;
import com.starlightnews.backend.global.client.FastApiProperties;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * 추천 가중치 재튜닝을 FastAPI 에 요청한다.
 *
 * <p>실패해도 예외를 올리지 않는다. 주 1회짜리라 한 번 걸러도 기존 가중치로 추천이 계속 돈다.
 */
@Slf4j
@Component
public class RecommendationRetuneClient {

	private static final String RETUNE_PATH = "/internal/v1/recommendations/retune";

	private final FastApiClient fastApiClient;

	public RecommendationRetuneClient(@Qualifier("fastApiRetuneRestClient") RestClient retuneRestClient,
			FastApiProperties fastApiProperties, ObjectMapper objectMapper) {
		this.fastApiClient = new FastApiClient(retuneRestClient, fastApiProperties, objectMapper);
	}

	/**
	 * 재튜닝을 요청한다. 지금 적용 중인 가중치를 실어 보내면 FastAPI 가 그 값 기준 ±0.1 안에서만 새 값을 고른다.
	 *
	 * @return 계산된 가중치. 실패하면 비어 있다
	 */
	public Optional<RecommendationRetuneResponse.Data> retune(RecommendationWeights current) {
		try {
			RecommendationRetuneResponse response = fastApiClient.post(
					RETUNE_PATH, RecommendationRetuneRequest.from(current), RecommendationRetuneResponse.class);
			return Optional.ofNullable(response).map(RecommendationRetuneResponse::data);
		} catch (BusinessException failure) {
			log.warn("추천 가중치 재튜닝 실패 (원인={}). 기존 가중치를 유지합니다.",
					failure.getErrorCode().getCode());
			return Optional.empty();
		}
	}
}

package com.starlightnews.backend.domain.recommendation.service;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationParameter;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationWeights;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationParameterRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 추천 계산에 쓸 가중치를 고른다.
 *
 * <p>주 1회 재튜닝이 쌓아 둔 것 중 가장 최근 값을 쓴다. 아직 한 번도 재튜닝하지 않았거나 조회가
 * 실패하면 기본값으로 돈다. 가중치 때문에 추천 회차가 통째로 비는 일은 없어야 한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationWeightProvider {

	private final RecommendationParameterRepository parameterRepository;

	@Transactional(readOnly = true)
	public RecommendationWeights current() {
		try {
			return parameterRepository.findFirstByOrderByParameterIdDesc()
					.map(RecommendationParameter::weights)
					.orElseGet(() -> {
						log.info("재튜닝 결과가 없어 기본 가중치로 추천을 계산합니다. (cbf={}, cf={})",
								RecommendationWeights.DEFAULT.cbf(), RecommendationWeights.DEFAULT.cf());
						return RecommendationWeights.DEFAULT;
					});
		} catch (RuntimeException failure) {
			log.warn("추천 가중치를 읽지 못해 기본값으로 계산합니다.", failure);
			return RecommendationWeights.DEFAULT;
		}
	}
}

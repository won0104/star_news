package com.starlightnews.backend.domain.recommendation.repository;

import java.util.Optional;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationParameter;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RecommendationParameterRepository extends JpaRepository<RecommendationParameter, Long> {

	/** 가장 최근 재튜닝 결과. 추천 회차가 이 값을 쓴다. */
	Optional<RecommendationParameter> findFirstByOrderByParameterIdDesc();
}

package com.starlightnews.backend.domain.recommendation.repository;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationRun;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RecommendationRunRepository extends JpaRepository<RecommendationRun, Long> {
}

package com.starlightnews.backend.domain.recommendation.repository;

import java.util.List;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunChunk;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RecommendationRunChunkRepository extends JpaRepository<RecommendationRunChunk, Long> {

	List<RecommendationRunChunk> findByRunIdOrderByChunkNoAsc(Long runId);
}

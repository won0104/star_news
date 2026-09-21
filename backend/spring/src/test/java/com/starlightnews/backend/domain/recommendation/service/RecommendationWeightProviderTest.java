package com.starlightnews.backend.domain.recommendation.service;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationParameter;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationWeights;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationParameterRepository;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 추천 가중치 선택을 실제 MySQL 에서 확인한다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class RecommendationWeightProviderTest {

	private static final LocalDateTime COMPUTED_AT = LocalDateTime.of(2026, 9, 20, 3, 0);

	@Autowired
	private RecommendationWeightProvider weightProvider;

	@Autowired
	private RecommendationParameterRepository parameterRepository;

	@Autowired
	private EntityManager entityManager;

	private void save(String cbf, String cf, LocalDateTime computedAt) {
		parameterRepository.save(new RecommendationParameter(new BigDecimal(cbf), new BigDecimal(cf),
				new BigDecimal("0.4123"), new BigDecimal("0.5833"), new BigDecimal("0.3912"), computedAt));
		entityManager.flush();
	}

	@Test
	void 재튜닝_결과가_없으면_기본값을_쓴다() {
		// 첫 주에도 추천은 돌아야 한다.
		parameterRepository.deleteAll();
		entityManager.flush();

		assertThat(weightProvider.current()).isEqualTo(RecommendationWeights.DEFAULT);
	}

	@Test
	void 가장_최근_재튜닝_결과를_쓴다() {
		parameterRepository.deleteAll();
		save("0.6000", "0.4000", COMPUTED_AT.minusWeeks(1));
		save("0.8000", "0.2000", COMPUTED_AT);
		entityManager.clear();

		RecommendationWeights weights = weightProvider.current();

		assertThat(weights.cbf()).isEqualByComparingTo("0.8000");
		assertThat(weights.cf()).isEqualByComparingTo("0.2000");
	}

	@Test
	void 지난_결과도_지우지_않고_남긴다() {
		// 주차별로 가중치와 지표를 견주려면 이력이 있어야 한다.
		parameterRepository.deleteAll();
		save("0.6000", "0.4000", COMPUTED_AT.minusWeeks(1));
		save("0.8000", "0.2000", COMPUTED_AT);
		entityManager.clear();

		assertThat(parameterRepository.count()).isEqualTo(2);
	}
}

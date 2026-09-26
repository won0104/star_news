package com.starlightnews.backend.domain.recommendation.service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Optional;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationParameter;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationWeights;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationRetuneResponse;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationParameterRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class RecommendationRetuneServiceTest {

	private static final LocalDateTime NOW = LocalDateTime.of(2026, 9, 27, 3, 0);
	private static final RecommendationWeights CURRENT = RecommendationWeights.DEFAULT;

	@Mock
	private RecommendationRetuneClient retuneClient;

	@Mock
	private RecommendationParameterRepository parameterRepository;

	@Mock
	private RecommendationWeightProvider weightProvider;

	@InjectMocks
	private RecommendationRetuneService service;

	private void givenResult(String cbf, String cf) {
		given(weightProvider.current()).willReturn(CURRENT);
		given(retuneClient.retune(CURRENT)).willReturn(Optional.of(new RecommendationRetuneResponse.Data(
				new BigDecimal(cbf), new BigDecimal(cf),
				new BigDecimal("0.4123"), new BigDecimal("0.5833"), new BigDecimal("0.3912"))));
	}

	@Test
	void 계산된_가중치를_저장한다() {
		givenResult("0.8000", "0.2000");

		assertThat(service.retune(NOW)).isTrue();

		ArgumentCaptor<RecommendationParameter> captor =
				ArgumentCaptor.forClass(RecommendationParameter.class);
		verify(parameterRepository).save(captor.capture());
		assertThat(captor.getValue().getCbfWeight()).isEqualByComparingTo("0.8000");
		assertThat(captor.getValue().getCfWeight()).isEqualByComparingTo("0.2000");
		assertThat(captor.getValue().getComputedAt()).isEqualTo(NOW);
	}

	@Test
	void 평가_지표도_함께_남긴다() {
		givenResult("0.7000", "0.3000");

		service.retune(NOW);

		ArgumentCaptor<RecommendationParameter> captor =
				ArgumentCaptor.forClass(RecommendationParameter.class);
		verify(parameterRepository).save(captor.capture());
		assertThat(captor.getValue().getNdcgAt10()).isEqualByComparingTo("0.4123");
		assertThat(captor.getValue().getHitRateAt10()).isEqualByComparingTo("0.5833");
		assertThat(captor.getValue().getRecallAt10()).isEqualByComparingTo("0.3912");
	}

	@Test
	void 호출이_실패하면_아무것도_저장하지_않는다() {
		// 기존 가중치로 추천은 계속 돈다. 다음 주에 다시 시도한다.
		given(weightProvider.current()).willReturn(CURRENT);
		given(retuneClient.retune(CURRENT)).willReturn(Optional.empty());

		assertThat(service.retune(NOW)).isFalse();

		verify(parameterRepository, never()).save(any());
	}

	@Test
	void 가중치가_0에서_1_밖이면_저장하지_않는다() {
		// 이상한 값을 저장하면 다음 재튜닝까지 일주일 동안 그 값으로 추천이 나간다.
		givenResult("1.5000", "0.2000");

		assertThat(service.retune(NOW)).isFalse();

		verify(parameterRepository, never()).save(any());
	}

	@Test
	void 가중치가_비어_있으면_저장하지_않는다() {
		given(weightProvider.current()).willReturn(CURRENT);
		given(retuneClient.retune(CURRENT)).willReturn(Optional.of(new RecommendationRetuneResponse.Data(
				null, new BigDecimal("0.3000"), null, null, null)));

		assertThat(service.retune(NOW)).isFalse();

		verify(parameterRepository, never()).save(any());
	}

	@Test
	void 지표가_비어_있어도_가중치는_저장한다() {
		// 지표는 참고용이다. 없다고 가중치를 버릴 이유가 없다.
		given(weightProvider.current()).willReturn(CURRENT);
		given(retuneClient.retune(CURRENT)).willReturn(Optional.of(new RecommendationRetuneResponse.Data(
				new BigDecimal("0.6000"), new BigDecimal("0.4000"), null, null, null)));

		assertThat(service.retune(NOW)).isTrue();

		verify(parameterRepository).save(any());
	}
}

package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;

import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class RecommendationRetentionServiceTest {

	private static final LocalDateTime NOW = LocalDateTime.of(2026, 9, 15, 6, 5);

	@Mock
	private UserRecommendationRepository repository;

	private RecommendationRetentionService service(int retentionDays) {
		return new RecommendationRetentionService(repository,
				new RecommendationRetentionProperties(retentionDays));
	}

	private LocalDateTime capturedThreshold() {
		ArgumentCaptor<LocalDateTime> captor = ArgumentCaptor.forClass(LocalDateTime.class);
		verify(repository).deleteOlderThan(captor.capture());
		return captor.getValue();
	}

	@Test
	void 보관_기간만큼_거슬러_올라간_시각을_기준으로_지운다() {
		given(repository.deleteOlderThan(any())).willReturn(0);

		service(7).purgeExpired(NOW);

		assertThat(capturedThreshold()).isEqualTo(NOW.minusDays(7));
	}

	@Test
	void 설정한_보관_기간을_따른다() {
		given(repository.deleteOlderThan(any())).willReturn(0);

		service(3).purgeExpired(NOW);

		assertThat(capturedThreshold()).isEqualTo(NOW.minusDays(3));
	}

	@Test
	void 기본_보관_기간은_일주일이다() {
		given(repository.deleteOlderThan(any())).willReturn(0);

		service(0).purgeExpired(NOW);

		assertThat(capturedThreshold()).isEqualTo(NOW.minusDays(7));
	}

	@Test
	void 지운_건수를_돌려준다() {
		given(repository.deleteOlderThan(any())).willReturn(12);

		assertThat(service(7).purgeExpired(NOW)).isEqualTo(12);
	}
}

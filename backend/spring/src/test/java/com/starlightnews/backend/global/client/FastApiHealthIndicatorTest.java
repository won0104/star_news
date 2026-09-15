package com.starlightnews.backend.global.client;

import java.time.Duration;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.Status;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class FastApiHealthIndicatorTest {

	private static final String BASE_URL = "http://fastapi.test:8000";

	@Mock
	private FastApiClient fastApiClient;

	private FastApiHealthIndicator indicator(String apiKey) {
		return new FastApiHealthIndicator(fastApiClient,
				new FastApiProperties(BASE_URL, apiKey, Duration.ofSeconds(5)));
	}

	@Test
	void 응답하면_UP이다() {
		given(fastApiClient.isReachable()).willReturn(true);

		Health health = indicator("test-key").health();

		assertThat(health.getStatus()).isEqualTo(Status.UP);
		assertThat(health.getDetails()).containsEntry("baseUrl", BASE_URL);
	}

	@Test
	void 응답하지_않으면_DOWN이다() {
		given(fastApiClient.isReachable()).willReturn(false);

		assertThat(indicator("test-key").health().getStatus()).isEqualTo(Status.DOWN);
	}

	@Test
	void 내부_API_키가_없으면_확인하지_않고_UNKNOWN이다() {
		// AI 연동이 필요 없는 팀원의 로컬에서 앱 전체가 DOWN 으로 보이면 안 된다.
		Health health = indicator("").health();

		assertThat(health.getStatus()).isEqualTo(Status.UNKNOWN);
		verifyNoInteractions(fastApiClient);
	}
}

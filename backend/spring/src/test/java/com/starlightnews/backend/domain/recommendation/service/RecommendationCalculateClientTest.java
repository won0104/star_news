package com.starlightnews.backend.domain.recommendation.service;

import java.util.List;

import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateRequest;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse;
import com.starlightnews.backend.domain.recommendation.service.RecommendationCalculateOutcome.Calculated;
import com.starlightnews.backend.domain.recommendation.service.RecommendationCalculateOutcome.Failed;
import com.starlightnews.backend.global.client.FastApiClient;
import com.starlightnews.backend.global.client.InternalApiErrorCode;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class RecommendationCalculateClientTest {

	private static final String CALCULATE_PATH = "/internal/v1/recommendations/calculate";

	@Mock
	private FastApiClient fastApiClient;

	@InjectMocks
	private RecommendationCalculateClient client;

	private RecommendationCalculateRequest requestFor(long... userIds) {
		List<Long> ids = java.util.Arrays.stream(userIds).boxed().toList();
		return RecommendationCalculateRequest.of(ids, RecommendationCycle.AM, 10);
	}

	private RecommendationCalculateResponse response() {
		return new RecommendationCalculateResponse(
				new RecommendationCalculateResponse.Data("AM", List.of()));
	}

	@Test
	void 계산_결과를_그대로_돌려준다() {
		RecommendationCalculateResponse expected = response();
		given(fastApiClient.post(eq(CALCULATE_PATH), any(), eq(RecommendationCalculateResponse.class)))
				.willReturn(expected);

		assertThat(client.calculate(requestFor(1L, 2L))).isEqualTo(new Calculated(expected));
	}

	@Test
	void 조립한_요청을_그대로_전달한다() {
		RecommendationCalculateRequest request = requestFor(1L);
		given(fastApiClient.post(any(), any(), any())).willReturn(response());

		client.calculate(request);

		verify(fastApiClient).post(CALCULATE_PATH, request, RecommendationCalculateResponse.class);
	}

	@ParameterizedTest
	@EnumSource(InternalApiErrorCode.class)
	void 어떤_실패든_예외를_올리지_않고_원인을_돌려준다(InternalApiErrorCode errorCode) {
		// 묶음 하나가 실패해도 남은 묶음은 계속 보내야 한다. 원인은 회차 실행 기록에 남긴다.
		given(fastApiClient.post(any(), any(), any())).willThrow(new BusinessException(errorCode));

		assertThatCode(() -> assertThat(client.calculate(requestFor(1L, 2L))).isEqualTo(new Failed(errorCode)))
				.doesNotThrowAnyException();
	}

	@Test
	void 내부_API_오류가_아닌_코드는_원인_불명_실패로_본다() {
		given(fastApiClient.post(any(), any(), any()))
				.willThrow(new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR));

		assertThat(client.calculate(requestFor(1L)))
				.isEqualTo(new Failed(InternalApiErrorCode.INTERNAL_API_FAILED));
	}

	@Test
	void 보낼_사용자가_없으면_호출하지_않고_빈_결과를_준다() {
		// 실패로 돌려주면 빈 묶음 하나가 회차를 PARTIAL 로 만든다.
		assertThat(client.calculate(requestFor())).isInstanceOfSatisfying(Calculated.class,
				calculated -> assertThat(calculated.response().results()).isEmpty());

		verify(fastApiClient, never()).post(any(), any(), any());
	}
}

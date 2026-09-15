package com.starlightnews.backend.domain.usergraph.service;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest.UserGraphSyncUser;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncResponse;
import com.starlightnews.backend.global.client.FastApiClient;
import com.starlightnews.backend.global.client.InternalApiErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
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
class UserGraphSyncClientTest {

	private static final String SYNC_PATH = "/internal/v1/user-graph/sync";

	private static final OffsetDateTime AGGREGATED_AT =
			OffsetDateTime.of(2026, 9, 15, 5, 0, 0, 0, ZoneOffset.ofHours(9));

	@Mock
	private FastApiClient fastApiClient;

	@InjectMocks
	private UserGraphSyncClient syncClient;

	private UserGraphSyncRequest requestFor(long... userIds) {
		List<UserGraphSyncUser> users = java.util.Arrays.stream(userIds)
				.mapToObj(userId -> new UserGraphSyncUser(userId, List.of(), List.of(), List.of()))
				.toList();
		return new UserGraphSyncRequest(users, AGGREGATED_AT);
	}

	@Test
	void 성공하면_FastAPI가_알려준_건수를_그대로_돌려준다() {
		given(fastApiClient.post(eq(SYNC_PATH), any(), eq(UserGraphSyncResponse.class)))
				.willReturn(new UserGraphSyncResponse(new UserGraphSyncResponse.Data(3, 2, List.of())));

		assertThat(syncClient.send(requestFor(1L, 2L, 3L)))
				.isEqualTo(new UserGraphSyncResult(3, 2, 0));
	}

	@Test
	void 일부_사용자가_반영되지_않으면_실패_건수로_센다() {
		// 요청 자체는 200 이지만 그 안에 실패한 사용자가 섞여 있다.
		given(fastApiClient.post(any(), any(), any()))
				.willReturn(new UserGraphSyncResponse(new UserGraphSyncResponse.Data(3, 2,
						List.of(new UserGraphSyncResponse.Failure(3L, "GRAPH_REFERENCE_NOT_FOUND")))));

		assertThat(syncClient.send(requestFor(1L, 2L, 3L)))
				.isEqualTo(new UserGraphSyncResult(3, 2, 1));
	}

	@Test
	void 실패자_목록이_없어도_깨지지_않는다() {
		// FastAPI 가 failed 를 생략할 수 있다.
		given(fastApiClient.post(any(), any(), any()))
				.willReturn(new UserGraphSyncResponse(new UserGraphSyncResponse.Data(1, 1, null)));

		assertThat(syncClient.send(requestFor(1L))).isEqualTo(new UserGraphSyncResult(1, 1, 0));
	}

	@Test
	void 이미_최신이면_실패로_치지_않는다() {
		// FastAPI 는 전원이 이미 최신일 때 409 STALE_USER_GRAPH_SNAPSHOT 을 준다.
		given(fastApiClient.post(any(), any(), any()))
				.willThrow(new BusinessException(InternalApiErrorCode.INTERNAL_API_CONFLICT));

		assertThat(syncClient.send(requestFor(1L, 2L)))
				.isEqualTo(new UserGraphSyncResult(2, 0, 0));
	}

	@ParameterizedTest
	@EnumSource(value = InternalApiErrorCode.class, names = "INTERNAL_API_CONFLICT", mode = EnumSource.Mode.EXCLUDE)
	void 그_외_실패는_예외를_올리지_않고_실패_건수로_알린다(InternalApiErrorCode errorCode) {
		// 묶음 하나가 실패해도 남은 묶음은 계속 보내야 한다.
		given(fastApiClient.post(any(), any(), any())).willThrow(new BusinessException(errorCode));

		assertThatCode(() -> assertThat(syncClient.send(requestFor(1L, 2L)))
				.isEqualTo(new UserGraphSyncResult(0, 0, 2)))
				.doesNotThrowAnyException();
	}

	@Test
	void 보낼_사용자가_없으면_호출하지_않는다() {
		assertThat(syncClient.send(requestFor())).isEqualTo(UserGraphSyncResult.empty());

		verify(fastApiClient, never()).post(any(), any(), any());
	}

	@Test
	void 응답에_data가_없어도_깨지지_않는다() {
		given(fastApiClient.post(any(), any(), any())).willReturn(new UserGraphSyncResponse(null));

		assertThat(syncClient.send(requestFor(1L))).isEqualTo(new UserGraphSyncResult(0, 0, 0));
	}

	@Test
	void 조립한_요청을_그대로_전달한다() {
		UserGraphSyncRequest request = requestFor(1L);
		given(fastApiClient.post(any(), any(), any()))
				.willReturn(new UserGraphSyncResponse(new UserGraphSyncResponse.Data(1, 1, java.util.List.of())));

		syncClient.send(request);

		verify(fastApiClient).post(SYNC_PATH, request, UserGraphSyncResponse.class);
	}
}

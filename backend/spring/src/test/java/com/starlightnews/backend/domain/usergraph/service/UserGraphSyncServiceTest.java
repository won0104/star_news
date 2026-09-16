package com.starlightnews.backend.domain.usergraph.service;

import java.time.OffsetDateTime;
import java.util.List;

import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest;
import com.starlightnews.backend.domain.usergraph.repository.UserGraphAggregationRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class UserGraphSyncServiceTest {

	@Mock
	private UserGraphAggregationRepository aggregationRepository;

	@Mock
	private UserGraphRequestAssembler assembler;

	@Mock
	private UserGraphSyncClient syncClient;

	private UserGraphSyncService service;

	@BeforeEach
	void setUp() {
		service = new UserGraphSyncService(aggregationRepository, assembler, syncClient,
				new UserGraphSyncProperties(2));
	}

	/** 조립기는 이 테스트의 관심사가 아니므로, 받은 ID 를 그대로 담은 요청을 돌려주게 둔다. */
	private void givenAssemblerEchoesUserIds() {
		given(assembler.assemble(any(), any())).willAnswer(invocation -> {
			List<Long> userIds = invocation.getArgument(0);
			OffsetDateTime aggregatedAt = invocation.getArgument(1);
			return new UserGraphSyncRequest(
					userIds.stream()
							.map(id -> new UserGraphSyncRequest.UserGraphSyncUser(
									id, List.of(), List.of(), List.of()))
							.toList(),
					aggregatedAt);
		});
	}

	@SafeVarargs
	private void givenUserPages(List<Long>... pages) {
		var stubbing = given(aggregationRepository.findSyncTargetUserIds(any(Pageable.class)));
		for (List<Long> page : pages) {
			stubbing = stubbing.willReturn(page);
		}
		stubbing.willReturn(List.of());
	}

	@Test
	void 전체_사용자를_묶음으로_나눠_보낸다() {
		givenUserPages(List.of(1L, 2L), List.of(3L));
		givenAssemblerEchoesUserIds();
		given(syncClient.send(any())).willReturn(new UserGraphSyncResult(2, 2, 0),
				new UserGraphSyncResult(1, 1, 0));

		UserGraphSyncResult result = service.sync();

		assertThat(result).isEqualTo(new UserGraphSyncResult(3, 3, 0));
		verify(syncClient, times(2)).send(any());
	}

	@Test
	void 모든_묶음이_같은_집계_시각을_쓴다() {
		// 묶음마다 새로 찍으면 FastAPI 의 낙관적 락 기준이 흔들린다.
		givenUserPages(List.of(1L, 2L), List.of(3L));
		givenAssemblerEchoesUserIds();
		given(syncClient.send(any())).willReturn(UserGraphSyncResult.empty());

		service.sync();

		ArgumentCaptor<OffsetDateTime> captor = ArgumentCaptor.forClass(OffsetDateTime.class);
		verify(assembler, times(2)).assemble(any(), captor.capture());
		assertThat(captor.getAllValues()).hasSize(2);
		assertThat(java.util.Set.copyOf(captor.getAllValues())).hasSize(1);
	}

	@Test
	void 묶음_하나가_실패해도_나머지를_계속_보낸다() {
		givenUserPages(List.of(1L, 2L), List.of(3L, 4L));
		givenAssemblerEchoesUserIds();
		given(syncClient.send(any())).willReturn(UserGraphSyncResult.failed(2),
				new UserGraphSyncResult(2, 2, 0));

		assertThat(service.sync()).isEqualTo(new UserGraphSyncResult(2, 2, 2));
	}

	@Test
	void 설정한_묶음_크기로_페이지를_읽는다() {
		givenUserPages(List.of(1L, 2L));
		givenAssemblerEchoesUserIds();
		given(syncClient.send(any())).willReturn(UserGraphSyncResult.empty());

		service.sync();

		ArgumentCaptor<Pageable> captor = ArgumentCaptor.forClass(Pageable.class);
		verify(aggregationRepository, times(2)).findSyncTargetUserIds(captor.capture());
		assertThat(captor.getAllValues()).containsExactly(PageRequest.of(0, 2), PageRequest.of(1, 2));
	}

	@Test
	void 사용자가_없으면_아무것도_보내지_않는다() {
		given(aggregationRepository.findSyncTargetUserIds(any(Pageable.class))).willReturn(List.of());

		assertThat(service.sync()).isEqualTo(UserGraphSyncResult.empty());

		verify(syncClient, never()).send(any());
	}
}

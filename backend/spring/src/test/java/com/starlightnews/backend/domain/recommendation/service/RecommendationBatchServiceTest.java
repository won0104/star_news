package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationCycleWindow;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateRequest;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationTargetRepository;
import com.starlightnews.backend.domain.recommendation.service.RecommendationCalculateOutcome.Calculated;
import com.starlightnews.backend.domain.recommendation.service.RecommendationCalculateOutcome.Failed;
import com.starlightnews.backend.global.client.InternalApiErrorCode;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class RecommendationBatchServiceTest {

	private static final LocalDateTime MORNING_RUN = LocalDateTime.of(2026, 9, 15, 5, 30);
	private static final LocalDateTime AVAILABLE_AT = LocalDateTime.of(2026, 9, 15, 6, 0);
	private static final Long RUN_ID = 42L;

	@Mock
	private RecommendationTargetRepository targetRepository;

	@Mock
	private RecommendationCalculateClient calculateClient;

	@Mock
	private RecommendationStoreService storeService;

	@Mock
	private EventSummaryService summaryService;

	@Mock
	private RecommendationRetentionService retentionService;

	@Mock
	private RecommendationRunRecorder runRecorder;

	private RecommendationBatchService service;

	@BeforeEach
	void setUp() {
		// 보관 7일, 묶음 2명, 사용자별 10건
		service = new RecommendationBatchService(targetRepository, calculateClient, storeService,
				summaryService, retentionService, runRecorder, new RecommendationProperties(7, 2, 10));
	}

	private RecommendationCalculateResponse response() {
		return new RecommendationCalculateResponse(
				new RecommendationCalculateResponse.Data("AM", List.of()));
	}

	private RecommendationCalculateOutcome calculated() {
		return new Calculated(response());
	}

	private RecommendationCalculateOutcome failed() {
		return new Failed(InternalApiErrorCode.INTERNAL_API_UNAVAILABLE);
	}

	@SafeVarargs
	private void givenUserPages(List<Long>... pages) {
		var stubbing = given(targetRepository.findTargetUserIds(any(Pageable.class)));
		for (List<Long> page : pages) {
			stubbing = stubbing.willReturn(page);
		}
		stubbing.willReturn(List.of());
	}

	private void givenCalculateSucceeds() {
		given(calculateClient.calculate(any())).willReturn(calculated());
	}

	@Test
	void 전체_사용자를_묶음으로_나눠_계산한다() {
		givenUserPages(List.of(1L, 2L), List.of(3L));
		givenCalculateSucceeds();
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(new RecommendationStoreResult(2, 6, 0),
						new RecommendationStoreResult(1, 3, 0));

		RecommendationBatchResult result = service.generate(MORNING_RUN);

		assertThat(result).isEqualTo(new RecommendationBatchResult(3, 9, 0, 0));
		verify(calculateClient, times(2)).calculate(any());
	}

	@Test
	void 모든_묶음이_같은_회차_시각을_쓴다() {
		// 묶음마다 새로 정하면 공개 시각이 갈려 한 회차가 여러 개로 쪼개진다.
		givenUserPages(List.of(1L, 2L), List.of(3L));
		givenCalculateSucceeds();
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(RecommendationStoreResult.empty());

		service.generate(MORNING_RUN);

		ArgumentCaptor<RecommendationCycleWindow> captor =
				ArgumentCaptor.forClass(RecommendationCycleWindow.class);
		verify(storeService, times(2)).store(any(RecommendationCalculateResponse.class), captor.capture());
		assertThat(Set.copyOf(captor.getAllValues())).hasSize(1);
		assertThat(captor.getAllValues().get(0).availableAt()).isEqualTo(AVAILABLE_AT);
	}

	@Test
	void 설정한_회차와_건수로_요청을_만든다() {
		givenUserPages(List.of(1L, 2L));
		givenCalculateSucceeds();
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(RecommendationStoreResult.empty());

		service.generate(MORNING_RUN);

		ArgumentCaptor<RecommendationCalculateRequest> captor =
				ArgumentCaptor.forClass(RecommendationCalculateRequest.class);
		verify(calculateClient).calculate(captor.capture());
		assertThat(captor.getValue().cycle()).isEqualTo(RecommendationCycle.AM);
		assertThat(captor.getValue().users())
				.extracting(RecommendationCalculateRequest.UserRequest::limit)
				.containsOnly(10);
	}

	@Test
	void 묶음_계산이_실패해도_나머지를_계속한다() {
		givenUserPages(List.of(1L, 2L), List.of(3L, 4L));
		given(calculateClient.calculate(any()))
				.willReturn(failed(), calculated());
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(new RecommendationStoreResult(2, 6, 0));

		RecommendationBatchResult result = service.generate(MORNING_RUN);

		assertThat(result.failedUsers()).isEqualTo(2);
		assertThat(result.storedUsers()).isEqualTo(2);
	}

	@Test
	void 계산에_실패한_묶음은_저장하지_않는다() {
		givenUserPages(List.of(1L, 2L));
		given(calculateClient.calculate(any())).willReturn(failed());

		service.generate(MORNING_RUN);

		verify(storeService, never()).store(any(RecommendationCalculateResponse.class), any());
	}

	@Test
	void 설정한_묶음_크기로_페이지를_읽는다() {
		givenUserPages(List.of(1L, 2L));
		givenCalculateSucceeds();
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(RecommendationStoreResult.empty());

		service.generate(MORNING_RUN);

		ArgumentCaptor<Pageable> captor = ArgumentCaptor.forClass(Pageable.class);
		verify(targetRepository, times(2)).findTargetUserIds(captor.capture());
		assertThat(captor.getAllValues()).containsExactly(PageRequest.of(0, 2), PageRequest.of(1, 2));
	}

	@Test
	void 회차가_끝나면_보관_정리를_한_번_한다() {
		// 묶음마다 부르면 같은 삭제를 반복한다.
		givenUserPages(List.of(1L, 2L), List.of(3L));
		givenCalculateSucceeds();
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(RecommendationStoreResult.empty());

		service.generate(MORNING_RUN);

		verify(retentionService, times(1)).purgeExpired(MORNING_RUN);
	}

	@Test
	void 사용자가_없어도_보관_정리는_한다() {
		given(targetRepository.findTargetUserIds(any(Pageable.class))).willReturn(List.of());

		assertThat(service.generate(MORNING_RUN)).isEqualTo(RecommendationBatchResult.empty());

		verify(calculateClient, never()).calculate(any());
		verify(retentionService).purgeExpired(MORNING_RUN);
	}

	@Test
	void 오후에_돌면_PM_회차로_요청한다() {
		givenUserPages(List.of(1L));
		givenCalculateSucceeds();
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(RecommendationStoreResult.empty());

		service.generate(LocalDateTime.of(2026, 9, 15, 17, 30));

		ArgumentCaptor<RecommendationCalculateRequest> captor =
				ArgumentCaptor.forClass(RecommendationCalculateRequest.class);
		verify(calculateClient).calculate(captor.capture());
		assertThat(captor.getValue().cycle()).isEqualTo(RecommendationCycle.PM);
	}

	@Test
	void 회차를_저장한_뒤_요약을_만든다() {
		// 공개까지 30분이 남아 있다. 그 사이에 만들어 둬야 조회가 요약을 기다리지 않는다.
		givenUserPages(List.of(1L));
		givenCalculateSucceeds();
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(RecommendationStoreResult.empty());

		service.generate(MORNING_RUN);

		verify(summaryService).generateForCycle(AVAILABLE_AT);
	}

	// --- 실행 기록 ---

	@Test
	void 회차_시작과_끝을_기록한다() {
		given(runRecorder.start(any(), any())).willReturn(RUN_ID);
		givenUserPages(List.of(1L, 2L), List.of(3L));
		givenCalculateSucceeds();
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(new RecommendationStoreResult(2, 6, 0), new RecommendationStoreResult(1, 3, 0));

		service.generate(MORNING_RUN);

		verify(runRecorder).start(RecommendationCycleWindow.from(MORNING_RUN), MORNING_RUN);
		verify(runRecorder).succeeded(RUN_ID, 0, List.of(1L, 2L));
		verify(runRecorder).succeeded(RUN_ID, 1, List.of(3L));
		verify(runRecorder).finish(eq(RUN_ID), eq(2), eq(0), eq(3),
				eq(new RecommendationBatchResult(3, 9, 0, 0)), any());
	}

	@Test
	void 계산에_실패한_묶음은_원인과_사용자를_기록한다() {
		// 사용자 목록이 있어야 나중에 같은 사람들로 다시 보낼 수 있다.
		given(runRecorder.start(any(), any())).willReturn(RUN_ID);
		givenUserPages(List.of(1L, 2L), List.of(3L, 4L));
		given(calculateClient.calculate(any())).willReturn(failed(), calculated());
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(new RecommendationStoreResult(2, 6, 0));

		service.generate(MORNING_RUN);

		verify(runRecorder).failed(RUN_ID, 0, List.of(1L, 2L), "INTERNAL_API_UNAVAILABLE");
		verify(runRecorder).succeeded(RUN_ID, 1, List.of(3L, 4L));
		verify(runRecorder).finish(eq(RUN_ID), eq(2), eq(1), eq(4), any(), any());
	}

	@Test
	void 저장이_실패한_묶음도_실패로_기록하고_다음_묶음을_계속한다() {
		// 저장은 묶음 단위 트랜잭션이라 이 묶음만 되돌아간다. 회차를 멈출 이유가 없다.
		given(runRecorder.start(any(), any())).willReturn(RUN_ID);
		givenUserPages(List.of(1L, 2L), List.of(3L));
		givenCalculateSucceeds();
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willThrow(new IllegalStateException("저장 실패"))
				.willReturn(new RecommendationStoreResult(1, 3, 0));

		RecommendationBatchResult result = service.generate(MORNING_RUN);

		assertThat(result).isEqualTo(new RecommendationBatchResult(1, 3, 0, 2));
		verify(runRecorder).failed(RUN_ID, 0, List.of(1L, 2L), RecommendationBatchService.STORE_FAILED);
		verify(runRecorder).succeeded(RUN_ID, 1, List.of(3L));
	}

	@Test
	void 사용자가_없으면_묶음_없이_끝난_회차로_기록한다() {
		given(runRecorder.start(any(), any())).willReturn(RUN_ID);
		given(targetRepository.findTargetUserIds(any(Pageable.class))).willReturn(List.of());

		service.generate(MORNING_RUN);

		verify(runRecorder).finish(eq(RUN_ID), eq(0), eq(0), eq(0),
				eq(RecommendationBatchResult.empty()), any());
	}

	@Test
	void 묶음_바깥에서_실패하면_중단으로_기록하고_예외를_올린다() {
		// RUNNING 으로 남기면 끝난 회차인지 도는 중인지 구분할 수 없다.
		given(runRecorder.start(any(), any())).willReturn(RUN_ID);
		given(targetRepository.findTargetUserIds(any(Pageable.class)))
				.willThrow(new IllegalStateException("DB 연결 끊김"));

		assertThatThrownBy(() -> service.generate(MORNING_RUN)).isInstanceOf(IllegalStateException.class);

		verify(runRecorder).abort(eq(RUN_ID), any());
		verify(runRecorder, never()).finish(any(), anyInt(), anyInt(), anyInt(), any(), any());
		verify(summaryService, never()).generateForCycle(any());
	}

	@Test
	void 사용자가_없으면_요약도_만들_것이_없다() {
		given(targetRepository.findTargetUserIds(any(Pageable.class))).willReturn(List.of());

		service.generate(MORNING_RUN);

		// 대상이 없으면 서비스가 스스로 빈 목록을 보고 끝낸다. 회차 시각은 그대로 넘긴다.
		verify(summaryService).generateForCycle(AVAILABLE_AT);
	}
}

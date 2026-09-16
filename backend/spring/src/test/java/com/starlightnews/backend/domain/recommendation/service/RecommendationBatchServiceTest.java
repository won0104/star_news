package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationCycleWindow;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateRequest;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationTargetRepository;
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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class RecommendationBatchServiceTest {

	private static final LocalDateTime MORNING_RUN = LocalDateTime.of(2026, 9, 15, 5, 30);
	private static final LocalDateTime AVAILABLE_AT = LocalDateTime.of(2026, 9, 15, 6, 0);

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

	private RecommendationBatchService service;

	@BeforeEach
	void setUp() {
		// 보관 7일, 묶음 2명, 사용자별 10건
		service = new RecommendationBatchService(targetRepository, calculateClient, storeService,
				summaryService, retentionService, new RecommendationProperties(7, 2, 10));
	}

	private RecommendationCalculateResponse response() {
		return new RecommendationCalculateResponse(
				new RecommendationCalculateResponse.Data("AM", List.of()));
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
		given(calculateClient.calculate(any())).willReturn(Optional.of(response()));
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
				.willReturn(Optional.empty(), Optional.of(response()));
		given(storeService.store(any(RecommendationCalculateResponse.class), any()))
				.willReturn(new RecommendationStoreResult(2, 6, 0));

		RecommendationBatchResult result = service.generate(MORNING_RUN);

		assertThat(result.failedUsers()).isEqualTo(2);
		assertThat(result.storedUsers()).isEqualTo(2);
	}

	@Test
	void 계산에_실패한_묶음은_저장하지_않는다() {
		givenUserPages(List.of(1L, 2L));
		given(calculateClient.calculate(any())).willReturn(Optional.empty());

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

	@Test
	void 사용자가_없으면_요약도_만들_것이_없다() {
		given(targetRepository.findTargetUserIds(any(Pageable.class))).willReturn(List.of());

		service.generate(MORNING_RUN);

		// 대상이 없으면 서비스가 스스로 빈 목록을 보고 끝낸다. 회차 시각은 그대로 넘긴다.
		verify(summaryService).generateForCycle(AVAILABLE_AT);
	}
}

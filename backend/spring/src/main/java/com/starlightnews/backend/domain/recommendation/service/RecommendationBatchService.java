package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationCycleWindow;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunStatus;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateRequest;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationTargetRepository;
import com.starlightnews.backend.domain.recommendation.service.RecommendationCalculateOutcome.Calculated;
import com.starlightnews.backend.domain.recommendation.service.RecommendationCalculateOutcome.Failed;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

/**
 * 한 회차의 추천을 끝까지 생성한다.
 *
 * <p>전체 사용자를 묶음으로 나눠 FastAPI 에 계산을 맡기고 결과를 저장한다. 묶음 하나가 실패해도
 * 나머지는 계속 처리하고, 회차가 끝나면 보관 기간이 지난 회차를 정리한다.
 *
 * <p>회차와 묶음의 결과는 {@link RecommendationRunRecorder} 로 남긴다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationBatchService {

	/** 저장 중 예외로 실패한 묶음의 실패 원인. 계산 실패는 내부 API 오류 코드를 쓴다. */
	static final String STORE_FAILED = "STORE_FAILED";

	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

	private final RecommendationTargetRepository targetRepository;
	private final RecommendationCalculateClient calculateClient;
	private final RecommendationStoreService storeService;
	private final EventSummaryService summaryService;
	private final RecommendationRetentionService retentionService;
	private final RecommendationRunRecorder runRecorder;
	private final RecommendationProperties properties;

	/**
	 * 회차를 실행한다.
	 *
	 * <p>회차 시각은 시작 시점 하나를 모든 묶음이 공유한다. 묶음마다 새로 정하면 공개 시각이 갈려
	 * 한 회차가 여러 개로 쪼개지고, 조회 API 가 그중 하나만 보여 준다.
	 *
	 * @param now 회차를 시작한 시각
	 */
	public RecommendationBatchResult generate(LocalDateTime now) {
		RecommendationCycleWindow window = RecommendationCycleWindow.from(now);
		Long runId = runRecorder.start(window, now);

		RecommendationBatchResult total = RecommendationBatchResult.empty();
		int chunks = 0;
		int failedChunks = 0;
		int targetUsers = 0;

		try {
			for (int page = 0; ; page++) {
				List<Long> userIds = targetRepository
						.findTargetUserIds(PageRequest.of(page, properties.chunkSize()));
				if (userIds.isEmpty()) {
					break;
				}

				RecommendationBatchResult chunk = process(runId, page, userIds, window);
				chunks++;
				targetUsers += userIds.size();
				if (chunk.failedUsers() > 0) {
					failedChunks++;
				}
				total = total.plus(chunk);
			}
		} catch (RuntimeException failure) {
			// 사용자 조회 같은 묶음 바깥의 실패다. RUNNING 으로 남기면 끝난 회차인지 알 수 없다.
			runRecorder.abort(runId, LocalDateTime.now(SEOUL));
			log.error("추천 생성 회차 중단: 회차 {}, 공개 {}, 처리한 묶음 {}개",
					window.cycle(), window.availableAt(), chunks, failure);
			throw failure;
		}

		runRecorder.finish(runId, chunks, failedChunks, targetUsers, total, LocalDateTime.now(SEOUL));

		// 요약은 회차를 다 저장한 뒤에 만든다. 공개까지 30분이 남아 있고, Event 단위라 묶음마다
		// 만들면 같은 Event 를 여러 번 부르게 된다.
		int summaries = summaryService.generateForCycle(window.availableAt());

		retentionService.purgeExpired(now);

		log.info("추천 생성 회차 종료: 회차 {}, 공개 {}, 상태 {}, 묶음 {}개 중 실패 {}개, 사용자 {}명, 추천 {}건, "
						+ "건너뜀 {}건, 실패 {}명, 요약 {}건",
				window.cycle(), window.availableAt(), RecommendationRunStatus.of(chunks, failedChunks),
				chunks, failedChunks, total.storedUsers(), total.storedItems(), total.skippedItems(),
				total.failedUsers(), summaries);
		return total;
	}

	/**
	 * 묶음 하나를 계산하고 저장한다. 계산이나 저장에 실패하면 그 사용자들만 실패로 센다.
	 *
	 * @return 이 묶음만의 결과
	 */
	private RecommendationBatchResult process(Long runId, int chunkNo, List<Long> userIds,
			RecommendationCycleWindow window) {
		RecommendationCalculateRequest request =
				RecommendationCalculateRequest.of(userIds, window.cycle(), properties.limitPerUser());

		return switch (calculateClient.calculate(request)) {
			case Calculated calculated -> store(runId, chunkNo, userIds, calculated, window);
			case Failed failed -> {
				runRecorder.failed(runId, chunkNo, userIds, failed.errorCode().getCode());
				yield RecommendationBatchResult.empty().plusFailed(userIds.size());
			}
		};
	}

	/**
	 * 계산 결과를 저장한다.
	 *
	 * <p>저장이 예외로 끝나도 회차는 이어 간다. 저장은 묶음 단위 트랜잭션이라 이 묶음만 되돌아가 있다.
	 */
	private RecommendationBatchResult store(Long runId, int chunkNo, List<Long> userIds,
			Calculated calculated, RecommendationCycleWindow window) {
		RecommendationStoreResult stored;
		try {
			stored = storeService.store(calculated.response(), window);
		} catch (RuntimeException failure) {
			log.warn("추천 저장 실패 (묶음 {}, 사용자 {}명)", chunkNo, userIds.size(), failure);
			runRecorder.failed(runId, chunkNo, userIds, STORE_FAILED);
			return RecommendationBatchResult.empty().plusFailed(userIds.size());
		}

		runRecorder.succeeded(runId, chunkNo, userIds);
		return RecommendationBatchResult.empty().plus(stored);
	}
}

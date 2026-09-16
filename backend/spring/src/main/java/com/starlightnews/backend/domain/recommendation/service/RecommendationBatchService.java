package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationCycleWindow;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateRequest;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationTargetRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

/**
 * 한 회차의 추천을 끝까지 생성한다.
 *
 * <p>전체 사용자를 묶음으로 나눠 FastAPI 에 계산을 맡기고 결과를 저장한다. 묶음 하나가 실패해도
 * 나머지는 계속 처리하고, 회차가 끝나면 보관 기간이 지난 회차를 정리한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationBatchService {

	private final RecommendationTargetRepository targetRepository;
	private final RecommendationCalculateClient calculateClient;
	private final RecommendationStoreService storeService;
	private final RecommendationRetentionService retentionService;
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
		RecommendationBatchResult total = RecommendationBatchResult.empty();

		for (int page = 0; ; page++) {
			List<Long> userIds = targetRepository
					.findTargetUserIds(PageRequest.of(page, properties.chunkSize()));
			if (userIds.isEmpty()) {
				break;
			}

			total = process(userIds, window, total);
		}

		retentionService.purgeExpired(now);

		log.info("추천 생성 회차 종료: 회차 {}, 공개 {}, 사용자 {}명, 추천 {}건, 건너뜀 {}건, 실패 {}명",
				window.cycle(), window.availableAt(), total.storedUsers(), total.storedItems(),
				total.skippedItems(), total.failedUsers());
		return total;
	}

	/** 묶음 하나를 계산하고 저장한다. 계산에 실패하면 그 사용자들만 실패로 센다. */
	private RecommendationBatchResult process(List<Long> userIds, RecommendationCycleWindow window,
			RecommendationBatchResult total) {
		RecommendationCalculateRequest request =
				RecommendationCalculateRequest.of(userIds, window.cycle(), properties.limitPerUser());

		return calculateClient.calculate(request)
				.map(response -> total.plus(storeService.store(response, window)))
				.orElseGet(() -> total.plusFailed(userIds.size()));
	}
}

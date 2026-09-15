package com.starlightnews.backend.domain.recommendation.service;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationCycleWindow;
import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse.Item;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse.UserResult;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationEventRepository;
import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import com.starlightnews.backend.global.enums.RecommendationType;
import com.starlightnews.backend.global.enums.TopicCode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 계산된 추천 결과를 MySQL 에 저장한다.
 *
 * <p>회차는 통째로 갈아끼운다.
 *
 * <p>묶음 하나를 한 트랜잭션으로 처리한다. 중간에 실패하면 그 묶음은 통째로 되돌아가고 다시 시도
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationStoreService {

	private final RecommendationEventRepository eventRepository;
	private final UserRecommendationRepository userRecommendationRepository;

	/**
	 * 사용자 묶음의 추천 결과를 한 회차로 저장한다.
	 *
	 * @param results 사용자별 추천 목록
	 * @param window  이 회차의 시각 정보
	 */
	@Transactional
	public RecommendationStoreResult store(List<UserResult> results, RecommendationCycleWindow window) {
		if (results.isEmpty()) {
			return RecommendationStoreResult.empty();
		}

		if (window.isReleasedImmediately()) {
			log.warn("공개 시각이 이미 지난 회차를 저장합니다. 저장 즉시 노출됩니다. (회차={}, 공개={})",
					window.cycle(), window.availableAt());
		}

		replaceCycle(results, window);

		int storedUsers = 0;
		int storedItems = 0;
		int skippedItems = 0;

		for (UserResult result : results) {
			List<UserRecommendation> recommendations = toRecommendations(result, window);
			skippedItems += result.items().size() - recommendations.size();
			if (recommendations.isEmpty()) {
				continue;
			}

			userRecommendationRepository.saveAll(recommendations);
			storedUsers++;
			storedItems += recommendations.size();
		}

		log.info("추천 회차 저장: 회차 {}, 사용자 {}명, 추천 {}건, 건너뜀 {}건",
				window.cycle(), storedUsers, storedItems, skippedItems);
		return new RecommendationStoreResult(storedUsers, storedItems, skippedItems);
	}

	/** 이번에 저장할 사용자들의 같은 회차 결과를 먼저 비운다. */
	private void replaceCycle(List<UserResult> results, RecommendationCycleWindow window) {
		List<Long> userIds = results.stream().map(UserResult::userId).toList();
		userRecommendationRepository.deleteCycle(userIds, window.availableAt());
	}

	/**
	 * 응답을 저장할 형태로 바꾼다. 형식이 맞지 않는 건은 빼고 로그를 남긴다.
	 *
	 * <p>한 건 때문에 묶음 전체가 실패하면 그 사용자들의 회차가 통째로 비어 버린다. FastAPI 가
	 * 새 유형을 추가하거나 값이 빠진 응답을 주더라도 나머지는 살린다.
	 */
	private List<UserRecommendation> toRecommendations(UserResult result, RecommendationCycleWindow window) {
		List<UserRecommendation> recommendations = new ArrayList<>();
		Set<String> seenEventIds = new HashSet<>();
		Set<String> seenRanks = new HashSet<>();

		for (Item item : result.items()) {
			if (!isComplete(item, result.userId())) {
				continue;
			}

			RecommendationType type = RecommendationType.from(item.recommendationType()).orElse(null);
			if (type == null) {
				log.warn("모르는 추천 유형이라 건너뜁니다. (userId={}, eventId={}, type={})",
						result.userId(), item.eventId(), item.recommendationType());
				continue;
			}
			if (TopicCode.from(item.topicCode()).isEmpty()) {
				log.warn("모르는 Topic 이라 건너뜁니다. (userId={}, eventId={}, topicCode={})",
						result.userId(), item.eventId(), item.topicCode());
				continue;
			}
			// 같은 회차 안에서 Event 와 순위는 각각 유일해야 한다. 중복이 오면 묶음 전체가 실패한다.
			if (!seenEventIds.add(type + "|" + item.eventId()) || !seenRanks.add(type + "|" + item.rank())) {
				log.warn("이미 쓴 Event 나 순위라 건너뜁니다. (userId={}, eventId={}, rank={})",
						result.userId(), item.eventId(), item.rank());
				continue;
			}

			eventRepository.upsert(item.eventId(), item.label(), item.topicCode());
			recommendations.add(new UserRecommendation(
					result.userId(), item.eventId(), type, item.score(), item.rank(), item.reason(),
					window.recommendedAt(), window.cycle(), window.availableAt()));
		}
		return recommendations;
	}

	private boolean isComplete(Item item, Long userId) {
		boolean complete = item.eventId() != null && !item.eventId().isBlank()
				&& item.label() != null && !item.label().isBlank()
				&& item.score() != null
				&& item.rank() != null;
		if (!complete) {
			log.warn("값이 빠진 추천이라 건너뜁니다. (userId={}, eventId={})", userId, item.eventId());
		}
		return complete;
	}
}

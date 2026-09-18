package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationEvent;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunStatus;
import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationBoardResponse;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationEventRepository;
import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 사용자에게 공개된 최신 추천 회차를 조회한다.
 *
 * <p>추천은 실시간으로 계산하지 않는다. 05:30·17:30 에 미리 만들어 두고 06:00·18:00 에 공개하므로,
 * 조회는 이미 쌓인 결과 중 공개 시각이 지났고 실행이 끝난 가장 최근 회차를 고르는 일이다.
 */
@Service
@RequiredArgsConstructor
public class RecommendationBoardService {

	/** DB DATETIME(6) 은 KST 벽시계로 저장되므로 응답 시 +09:00 오프셋을 붙인다. */
	private static final ZoneId KST_ZONE = ZoneId.of("Asia/Seoul");
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	private final UserRecommendationRepository userRecommendationRepository;
	private final RecommendationEventRepository eventRepository;

	/**
	 * 공개된 최신 회차의 추천을 순위 순으로 조회한다.
	 *
	 * @return 공개된 회차가 없으면 빈 응답
	 */
	@Transactional(readOnly = true)
	public RecommendationBoardResponse getBoard(Long userId) {
		Optional<LocalDateTime> availableAt = userRecommendationRepository
				.findLatestAvailableAt(userId, LocalDateTime.now(KST_ZONE), RecommendationRunStatus.visible());
		if (availableAt.isEmpty()) {
			return RecommendationBoardResponse.empty();
		}

		List<UserRecommendation> cycle = userRecommendationRepository
				.findCycle(userId, availableAt.get());
		if (cycle.isEmpty()) {
			return RecommendationBoardResponse.empty();
		}

		UserRecommendation first = cycle.get(0);
		return new RecommendationBoardResponse(
				first.getCycle(),
				first.getRecommendedAt().atOffset(KST),
				availableAt.get().atOffset(KST),
				toItems(cycle));
	}

	private List<RecommendationBoardResponse.Item> toItems(List<UserRecommendation> cycle) {
		Map<String, RecommendationEvent> events = eventRepository
				.findAllById(cycle.stream().map(UserRecommendation::getEventId).toList()).stream()
				.collect(Collectors.toMap(RecommendationEvent::getEventId, Function.identity()));

		return cycle.stream().map(recommendation -> {
			RecommendationEvent event = events.get(recommendation.getEventId());
			return new RecommendationBoardResponse.Item(
					recommendation.getUserRecommendationId(),
					recommendation.getEventId(),
					event.getTitle(),
					event.getTopicCode(),
					recommendation.getRecommendationScore(),
					recommendation.getRank(),
					recommendation.getRecommendationType());
		}).toList();
	}
}

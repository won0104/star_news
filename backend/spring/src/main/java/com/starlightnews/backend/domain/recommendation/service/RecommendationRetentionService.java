package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;

import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 보관 기간이 지난 추천 회차를 지운다.
 *
 * <p>회차마다 한 번 부르면 된다. 묶음마다 부르면 같은 삭제를 여러 번 반복한다.
 *
 * <p>{@code recommendation_events} 는 지우지 않는다. 사용자별이 아니라 Event 별이고, 만들어 둔 요약을
 * 계속 재사용하기 때문이다. 지우면 같은 Event 가 다시 추천될 때 요약을 새로 만들어야 한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationRetentionService {

	private final UserRecommendationRepository userRecommendationRepository;
	private final RecommendationProperties properties;

	/**
	 * 보관 기간을 넘긴 회차를 지운다.
	 *
	 * @param now 기준 시각. 이 시점에서 보관 기간만큼 거슬러 올라간다
	 * @return 지운 추천 건수
	 */
	@Transactional
	public int purgeExpired(LocalDateTime now) {
		LocalDateTime threshold = now.minusDays(properties.retentionDays());
		int deleted = userRecommendationRepository.deleteOlderThan(threshold);

		if (deleted > 0) {
			log.info("보관 기간이 지난 추천 {}건을 정리했습니다. (기준={} 이전)", deleted, threshold);
		}
		return deleted;
	}
}

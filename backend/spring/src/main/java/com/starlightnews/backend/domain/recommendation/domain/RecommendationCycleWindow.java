package com.starlightnews.backend.domain.recommendation.domain;

import java.time.LocalDateTime;
import java.time.LocalTime;

import com.starlightnews.backend.global.enums.RecommendationCycle;

/**
 * 한 회차의 시각 정보. 계산 시각에서 회차와 공개 시각을 정한다.
 *
 * <p>추천은 05:30·17:30 에 계산해 06:00·18:00 에 공개한다. 계산과 공개 사이에 30분을 두는 이유는
 * 계산이 조금 늦어져도 공개 시각에는 결과가 준비돼 있게 하기 위해서다.
 *
 * @param recommendedAt 계산한 시각
 * @param availableAt   사용자에게 보이기 시작하는 시각
 */
public record RecommendationCycleWindow(
		RecommendationCycle cycle,
		LocalDateTime recommendedAt,
		LocalDateTime availableAt
) {

	/** 오전 회차 공개 시각. */
	private static final LocalTime AM_RELEASE = LocalTime.of(6, 0);

	/** 오후 회차 공개 시각. */
	private static final LocalTime PM_RELEASE = LocalTime.of(18, 0);

	/**
	 * 계산 시각으로 회차를 정한다.
	 *
	 * <p>정오를 기준으로 오전·오후를 가른다. 정해진 시각(05:30·17:30)에 돌지 않더라도 언제 돌렸든
	 * 회차가 하나로 정해져야, 재시도했을 때 같은 회차를 덮어쓴다.
	 *
	 * <p>공개 시각이 이미 지났으면 그대로 둔다. 배치가 늦어 06:10 에 끝났다면 06:00 으로 저장돼
	 * 즉시 공개된다
	 */
	public static RecommendationCycleWindow from(LocalDateTime recommendedAt) {
		boolean morning = recommendedAt.toLocalTime().isBefore(LocalTime.NOON);
		RecommendationCycle cycle = morning ? RecommendationCycle.AM : RecommendationCycle.PM;
		LocalDateTime availableAt = recommendedAt.toLocalDate()
				.atTime(morning ? AM_RELEASE : PM_RELEASE);

		return new RecommendationCycleWindow(cycle, recommendedAt, availableAt);
	}

	/** 저장 시점에 이미 공개 시각이 지났는지. 배치가 늦게 돌면 참이 된다. */
	public boolean isReleasedImmediately() {
		return !availableAt.isAfter(recommendedAt);
	}
}

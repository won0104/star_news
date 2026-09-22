package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.time.ZoneId;

import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 주 1회 추천 가중치를 다시 고른다. 일요일 03:00 (KST)
 *
 * <p>추천 회차(05:30·17:30)와 기사 분석 회차(매시 20분)를 피한 시각이다. 그리드서치가 몇 분 걸려
 * 다른 배치와 겹치면 서로 느려진다. 새 가중치는 같은 날 05:30 회차부터 쓰인다.
 */
@Component
@RequiredArgsConstructor
public class RecommendationRetuneScheduler {

	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

	private final RecommendationRetuneService retuneService;

	@Scheduled(cron = "${app.recommendation.retune.cron:0 0 3 * * SUN}", zone = "Asia/Seoul")
	public void retune() {
		retuneService.retune(LocalDateTime.now(SEOUL));
	}
}

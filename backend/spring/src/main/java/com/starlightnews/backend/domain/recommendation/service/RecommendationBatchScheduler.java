package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.time.ZoneId;

import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 하루 두 번 추천을 미리 계산해 둔다. 05:30 · 17:30 (KST)
 *
 * <p>계산 결과는 06:00 · 18:00 에 공개된다. 30분을 띄운 이유는 계산이 조금 늦어져도 공개 시각에는
 * 결과가 준비돼 있게 하기 위해서다.
 *
 * <p>직전 홀수 시 정각(05:00 · 17:00)에 사용자 그래프 동기화가 끝나 있어야 한다. FastAPI 는 그
 * 그래프만 보고 추천을 계산하므로, 동기화가 실패하면 낡은 상태로 계산된다.
 */
@Component
@RequiredArgsConstructor
public class RecommendationBatchScheduler {

	/** 회차 시각은 배치가 도는 시간대 기준으로 찍는다. 스케줄도 같은 시간대를 쓴다. */
	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

	private final RecommendationBatchService recommendationBatchService;

	@Scheduled(cron = "${app.recommendation.generate-cron:0 30 5,17 * * *}", zone = "Asia/Seoul")
	public void generate() {
		recommendationBatchService.generate(LocalDateTime.now(SEOUL));
	}
}

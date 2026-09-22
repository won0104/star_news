package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Stream;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.scheduling.support.CronExpression;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class RecommendationRetuneSchedulerTest {

	/** application.properties 의 기본값과 같아야 한다. */
	private static final String RETUNE_CRON = "0 0 3 * * SUN";

	/** 추천 계산 주기. 재튜닝은 이보다 먼저 끝나야 새 가중치가 그날부터 쓰인다. */
	private static final String GENERATE_CRON = "0 30 5,17 * * *";

	@Mock
	private RecommendationRetuneService retuneService;

	@InjectMocks
	private RecommendationRetuneScheduler scheduler;

	private List<LocalDateTime> nextRuns(String cron, LocalDateTime from, int count) {
		CronExpression expression = CronExpression.parse(cron);
		return Stream.iterate(expression.next(from), expression::next).limit(count).toList();
	}

	@Test
	void 스케줄이_돌면_재튜닝을_실행한다() {
		scheduler.retune();

		verify(retuneService).retune(any(LocalDateTime.class));
	}

	@Test
	void 일요일_새벽_3시에_주_1회_돈다() {
		List<LocalDateTime> runs = nextRuns(RETUNE_CRON, LocalDateTime.of(2026, 9, 21, 0, 0), 2);

		assertThat(runs).containsExactly(
				LocalDateTime.of(2026, 9, 27, 3, 0),
				LocalDateTime.of(2026, 10, 4, 3, 0));
	}

	@Test
	void 그날_추천_계산보다_먼저_돈다() {
		// 새 가중치는 같은 날 05:30 회차부터 쓰인다.
		LocalDateTime retune = nextRuns(RETUNE_CRON, LocalDateTime.of(2026, 9, 21, 0, 0), 1).get(0);
		LocalDateTime generate = nextRuns(GENERATE_CRON, retune, 1).get(0);

		assertThat(retune).isBefore(generate);
		assertThat(generate).isEqualTo(LocalDateTime.of(2026, 9, 27, 5, 30));
	}

	@Test
	void 기사_분석_회차와_겹치지_않는다() {
		// 분석은 매시 20분에 시작해 시간 예산까지 돈다. 정각에 시작하면 서로 느려진다.
		LocalDateTime retune = nextRuns(RETUNE_CRON, LocalDateTime.of(2026, 9, 21, 0, 0), 1).get(0);

		assertThat(retune.getMinute()).isZero();
	}
}

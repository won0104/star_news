package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.util.List;

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
class RecommendationBatchSchedulerTest {

	/** application.properties 의 기본값과 같아야 한다. */
	private static final String GENERATE_CRON = "0 30 5,17 * * *";

	/** 사용자 그래프 동기화 주기. 추천 계산 직전에 끝나 있어야 한다. */
	private static final String SYNC_CRON = "0 0 1-23/2 * * *";

	@Mock
	private RecommendationBatchService recommendationBatchService;

	@InjectMocks
	private RecommendationBatchScheduler scheduler;

	private List<LocalDateTime> nextRuns(String cron, LocalDateTime from, int count) {
		CronExpression expression = CronExpression.parse(cron);
		return java.util.stream.Stream.iterate(expression.next(from), expression::next)
				.limit(count)
				.toList();
	}

	@Test
	void 스케줄이_돌면_회차를_실행한다() {
		scheduler.generate();

		verify(recommendationBatchService).generate(any(LocalDateTime.class));
	}

	@Test
	void 하루에_05시_30분과_17시_30분에_돈다() {
		List<LocalDateTime> runs = nextRuns(GENERATE_CRON, LocalDateTime.of(2026, 9, 15, 0, 0), 2);

		assertThat(runs).containsExactly(
				LocalDateTime.of(2026, 9, 15, 5, 30),
				LocalDateTime.of(2026, 9, 15, 17, 30));
	}

	@Test
	void 공개_시각인_06시_18시보다_먼저_돈다() {
		// 늦으면 공개 시각에 결과가 준비되지 않는다.
		List<LocalDateTime> runs = nextRuns(GENERATE_CRON, LocalDateTime.of(2026, 9, 15, 0, 0), 2);

		assertThat(runs.get(0)).isBefore(LocalDateTime.of(2026, 9, 15, 6, 0));
		assertThat(runs.get(1)).isBefore(LocalDateTime.of(2026, 9, 15, 18, 0));
	}

	@Test
	void 사용자_그래프_동기화가_끝난_뒤에_돈다() {
		// FastAPI 는 그 그래프만 보고 계산한다. 순서가 뒤집히면 낡은 상태로 추천이 만들어진다.
		LocalDateTime midnight = LocalDateTime.of(2026, 9, 15, 0, 0);
		LocalDateTime firstGenerate = nextRuns(GENERATE_CRON, midnight, 1).get(0);

		LocalDateTime syncBefore = nextRuns(SYNC_CRON, midnight, 12).stream()
				.filter(run -> run.isBefore(firstGenerate))
				.reduce((first, second) -> second)
				.orElseThrow();

		assertThat(syncBefore).isEqualTo(LocalDateTime.of(2026, 9, 15, 5, 0));
		assertThat(syncBefore).isBefore(firstGenerate);
	}
}

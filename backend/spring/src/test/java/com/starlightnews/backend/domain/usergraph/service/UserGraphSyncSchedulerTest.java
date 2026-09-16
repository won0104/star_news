package com.starlightnews.backend.domain.usergraph.service;

import java.time.LocalDateTime;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.scheduling.support.CronExpression;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class UserGraphSyncSchedulerTest {

	/** application.properties 의 기본값과 같아야 한다. */
	private static final String SYNC_CRON = "0 0 1-23/2 * * *";

	@Mock
	private UserGraphSyncService userGraphSyncService;

	@InjectMocks
	private UserGraphSyncScheduler scheduler;

	@Test
	void 스케줄이_돌면_동기화를_실행한다() {
		scheduler.sync();

		verify(userGraphSyncService).sync();
	}

	@Test
	void 추천_계산_직전인_05시와_17시에_실행된다() {
		// 05:30·17:30 추천 계산이 이 결과를 읽는다. 빠지면 그 회차가 낡은 그래프로 계산된다.
		CronExpression cron = CronExpression.parse(SYNC_CRON);

		assertThat(nextRunHours(cron, LocalDateTime.of(2026, 9, 15, 0, 0), 12))
				.contains(5, 17);
	}

	@Test
	void 트렌드_집계가_쓰는_06시와_18시는_피한다() {
		CronExpression cron = CronExpression.parse(SYNC_CRON);

		assertThat(nextRunHours(cron, LocalDateTime.of(2026, 9, 15, 0, 0), 12))
				.doesNotContain(6, 18);
	}

	@Test
	void 두_시간_간격으로_돈다() {
		CronExpression cron = CronExpression.parse(SYNC_CRON);

		LocalDateTime first = cron.next(LocalDateTime.of(2026, 9, 15, 0, 0));
		assertThat(cron.next(first)).isEqualTo(first.plusHours(2));
	}

	private List<Integer> nextRunHours(CronExpression cron, LocalDateTime from, int count) {
		return java.util.stream.Stream.iterate(cron.next(from), cron::next)
				.limit(count)
				.map(LocalDateTime::getHour)
				.toList();
	}
}

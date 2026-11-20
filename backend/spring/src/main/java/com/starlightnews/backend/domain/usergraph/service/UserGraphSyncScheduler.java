package com.starlightnews.backend.domain.usergraph.service;

import lombok.RequiredArgsConstructor;
import net.javacrumbs.shedlock.spring.annotation.SchedulerLock;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 주기적으로 사용자 상태를 Neo4j User Graph 에 반영한다. 기본은 홀수 시 정각(KST)이다.
 */
@Component
@RequiredArgsConstructor
public class UserGraphSyncScheduler {

	private final UserGraphSyncService userGraphSyncService;

	// 100명 묶음마다 30초 타임아웃. 2시간 간격보다 짧게 둬서 잡은 인스턴스가 죽어도 다음 회차는 돈다.
	@Scheduled(cron = "${app.user-graph.sync-cron:0 0 1-23/2 * * *}", zone = "Asia/Seoul")
	@SchedulerLock(name = "user-graph-sync", lockAtMostFor = "90m", lockAtLeastFor = "5m")
	public void sync() {
		userGraphSyncService.sync();
	}
}

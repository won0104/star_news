package com.starlightnews.backend.domain.usergraph.service;

import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 주기적으로 사용자 상태를 Neo4j User Graph 에 반영한다. 기본은 홀수 시 정각(KST)이다.
 */
@Component
@RequiredArgsConstructor
public class UserGraphSyncScheduler {

	private final UserGraphSyncService userGraphSyncService;

	@Scheduled(cron = "${app.user-graph.sync-cron:0 0 1-23/2 * * *}", zone = "Asia/Seoul")
	public void sync() {
		userGraphSyncService.sync();
	}
}

package com.starlightnews.backend.domain.usergraph.service;

import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;

import com.starlightnews.backend.domain.usergraph.repository.UserGraphAggregationRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

/**
 * 한 회차의 User Graph 동기화를 끝까지 수행한다.
 *
 * <p>전체 사용자를 묶음으로 나눠 보낸다. 묶음 하나가 실패해도 나머지는 계속 보내고, 회차가 끝나면
 * 처리·갱신·실패 건수를 남긴다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserGraphSyncService {

	/** 집계 시각은 배치가 도는 시간대 기준으로 찍는다. 스케줄도 같은 시간대를 쓴다. */
	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

	private final UserGraphAggregationRepository aggregationRepository;
	private final UserGraphRequestAssembler assembler;
	private final UserGraphSyncClient syncClient;
	private final UserGraphSyncProperties properties;

	/**
	 * 회차를 실행한다.
	 *
	 * <p>집계 시각은 회차 시작 시점 하나를 모든 묶음이 공유한다. 묶음마다 새로 찍으면 FastAPI 의
	 * 낙관적 락 기준이 흔들려, 늦게 도착한 요청이 먼저 도착한 것을 덮어쓸 수 있다.
	 */
	public UserGraphSyncResult sync() {
		OffsetDateTime aggregatedAt = OffsetDateTime.now(SEOUL);
		UserGraphSyncResult total = UserGraphSyncResult.empty();

		for (int page = 0; ; page++) {
			List<Long> userIds = aggregationRepository
					.findSyncTargetUserIds(PageRequest.of(page, properties.chunkSize()));
			if (userIds.isEmpty()) {
				break;
			}

			total = total.plus(syncClient.send(assembler.assemble(userIds, aggregatedAt)));
		}

		log.info("User Graph 동기화 종료: 처리 {}명, 갱신 {}명, 실패 {}명",
				total.processedUsers(), total.updatedUsers(), total.failedUsers());
		return total;
	}
}

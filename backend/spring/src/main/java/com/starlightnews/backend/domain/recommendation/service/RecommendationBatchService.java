package com.starlightnews.backend.domain.recommendation.service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationCycleWindow;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunStatus;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateRequest;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationTargetRepository;
import com.starlightnews.backend.domain.recommendation.service.RecommendationCalculateOutcome.Calculated;
import com.starlightnews.backend.domain.recommendation.service.RecommendationCalculateOutcome.Failed;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

/**
 * 한 회차의 추천을 끝까지 생성한다.
 *
 * <p>전체 사용자를 묶음으로 나눠 FastAPI 에 계산을 맡기고 결과를 저장한다. 묶음 하나가 실패해도
 * 나머지는 계속 처리하고, 한 바퀴를 다 돈 뒤 일시적으로 실패한 묶음만 다시 보낸다. 회차가 끝나면
 * 보관 기간이 지난 회차를 정리한다.
 *
 * <p>회차와 묶음의 결과는 {@link RecommendationRunRecorder} 로 남긴다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationBatchService {

	/** 저장 중 예외로 실패한 묶음의 실패 원인. 계산 실패는 내부 API 오류 코드를 쓴다. */
	static final String STORE_FAILED = "STORE_FAILED";

	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

	private final RecommendationTargetRepository targetRepository;
	private final RecommendationCalculateClient calculateClient;
	private final RecommendationStoreService storeService;
	private final EventSummaryService summaryService;
	private final RecommendationRetentionService retentionService;
	private final RecommendationRunRecorder runRecorder;
	private final RecommendationProperties properties;

	/**
	 * 회차를 실행한다.
	 *
	 * <p>회차 시각은 시작 시점 하나를 모든 묶음이 공유한다. 묶음마다 새로 정하면 공개 시각이 갈려
	 * 한 회차가 여러 개로 쪼개지고, 조회 API 가 그중 하나만 보여 준다. 재시도도 같은 회차 시각으로
	 * 저장한다.
	 *
	 * @param now 회차를 시작한 시각
	 */
	public RecommendationBatchResult generate(LocalDateTime now) {
		RecommendationCycleWindow window = RecommendationCycleWindow.from(now);
		Long runId = runRecorder.start(window, now);
		List<Chunk> chunks = new ArrayList<>();

		try {
			for (int page = 0; ; page++) {
				List<Long> userIds = targetRepository
						.findTargetUserIds(PageRequest.of(page, properties.chunkSize()));
				if (userIds.isEmpty()) {
					break;
				}

				Chunk chunk = new Chunk(page, userIds, attempt(userIds, window));
				record(runId, chunk);
				chunks.add(chunk);
			}

			retryFailed(runId, chunks, window);
		} catch (RuntimeException failure) {
			// 사용자 조회 같은 묶음 바깥의 실패다. RUNNING 으로 남기면 끝난 회차인지 알 수 없다.
			runRecorder.abort(runId, LocalDateTime.now(SEOUL));
			log.error("추천 생성 회차 중단: 회차 {}, 공개 {}, 처리한 묶음 {}개",
					window.cycle(), window.availableAt(), chunks.size(), failure);
			throw failure;
		}

		RecommendationBatchResult total = chunks.stream()
				.map(chunk -> chunk.last.result())
				.reduce(RecommendationBatchResult.empty(), RecommendationBatchResult::plus);
		int failedChunks = (int) chunks.stream().filter(chunk -> !chunk.last.succeeded()).count();
		int recoveredChunks = (int) chunks.stream()
				.filter(chunk -> chunk.last.succeeded() && chunk.attempts > 1).count();
		int targetUsers = chunks.stream().mapToInt(chunk -> chunk.userIds.size()).sum();

		runRecorder.finish(runId, chunks.size(), failedChunks, targetUsers, total, LocalDateTime.now(SEOUL));

		// 요약은 회차를 다 저장한 뒤에 만든다. 공개까지 30분이 남아 있고, Event 단위라 묶음마다
		// 만들면 같은 Event 를 여러 번 부르게 된다.
		int summaries = summaryService.generateForCycle(window.availableAt());

		retentionService.purgeExpired(now);

		log.info("추천 생성 회차 종료: 회차 {}, 공개 {}, 상태 {}, 묶음 {}개 중 실패 {}개(재시도로 복구 {}개), "
						+ "사용자 {}명, 추천 {}건, 건너뜀 {}건, 실패 {}명, 요약 {}건",
				window.cycle(), window.availableAt(), RecommendationRunStatus.of(chunks.size(), failedChunks),
				chunks.size(), failedChunks, recoveredChunks, total.storedUsers(), total.storedItems(),
				total.skippedItems(), total.failedUsers(), summaries);
		return total;
	}

	/**
	 * 일시적으로 실패한 묶음만 다시 보낸다.
	 *
	 * <p>한 바퀴를 다 돈 뒤에 모아서 보낸다. 실패 직후 바로 다시 부르면 막힌 FastAPI 에 또 부딪치고,
	 * 기다리는 동안 뒤 묶음들이 밀린다. 사용자는 기록해 둔 목록 그대로 보낸다.
	 */
	private void retryFailed(Long runId, List<Chunk> chunks, RecommendationCycleWindow window) {
		for (int attemptNo = 2; attemptNo <= properties.maxAttempts(); attemptNo++) {
			List<Chunk> pending = chunks.stream()
					.filter(chunk -> !chunk.last.succeeded() && chunk.last.retryable())
					.toList();
			if (pending.isEmpty()) {
				return;
			}

			log.info("실패한 묶음 {}개를 {} 뒤 다시 보냅니다. ({}/{}번째 시도)",
					pending.size(), properties.retryDelay(), attemptNo, properties.maxAttempts());
			if (!waitBeforeRetry(properties.retryDelay())) {
				return;
			}

			for (Chunk chunk : pending) {
				chunk.retry(attempt(chunk.userIds, window));
				runRecorder.retried(runId, chunk.no, chunk.last.failureCode());
			}
		}
	}

	/** @return 기다렸으면 참. 서버 종료로 끊겼으면 거짓이고 재시도를 멈춘다 */
	private boolean waitBeforeRetry(Duration delay) {
		if (delay.isZero() || delay.isNegative()) {
			return true;
		}
		try {
			Thread.sleep(delay.toMillis());
			return true;
		} catch (InterruptedException interrupted) {
			Thread.currentThread().interrupt();
			log.warn("추천 재시도 대기 중 중단되어 남은 재시도를 건너뜁니다.");
			return false;
		}
	}

	private void record(Long runId, Chunk chunk) {
		if (chunk.last.succeeded()) {
			runRecorder.succeeded(runId, chunk.no, chunk.userIds);
		} else {
			runRecorder.failed(runId, chunk.no, chunk.userIds, chunk.last.failureCode());
		}
	}

	/** 묶음 하나를 계산하고 저장한다. 계산이나 저장에 실패하면 그 사용자들만 실패로 센다. */
	private ChunkAttempt attempt(List<Long> userIds, RecommendationCycleWindow window) {
		RecommendationCalculateRequest request =
				RecommendationCalculateRequest.of(userIds, window.cycle(), properties.limitPerUser());

		return switch (calculateClient.calculate(request)) {
			case Calculated calculated -> store(userIds, calculated, window);
			case Failed failed -> ChunkAttempt.failed(userIds.size(), failed.errorCode().getCode(),
					failed.retryable());
		};
	}

	/**
	 * 계산 결과를 저장한다.
	 *
	 * <p>저장이 예외로 끝나도 회차는 이어 간다. 저장은 묶음 단위 트랜잭션이라 이 묶음만 되돌아가 있어
	 * 다시 보내도 안전하다.
	 */
	private ChunkAttempt store(List<Long> userIds, Calculated calculated, RecommendationCycleWindow window) {
		try {
			return ChunkAttempt.succeeded(storeService.store(calculated.response(), window));
		} catch (RuntimeException failure) {
			log.warn("추천 저장 실패 (사용자 {}명)", userIds.size(), failure);
			return ChunkAttempt.failed(userIds.size(), STORE_FAILED, true);
		}
	}

	/**
	 * 묶음 한 번 시도의 결과.
	 *
	 * @param failureCode 실패 원인. 성공했으면 {@code null}
	 * @param retryable   같은 회차 안에서 다시 보낼 만한 실패인지
	 */
	private record ChunkAttempt(RecommendationBatchResult result, String failureCode, boolean retryable) {

		static ChunkAttempt succeeded(RecommendationStoreResult stored) {
			return new ChunkAttempt(RecommendationBatchResult.empty().plus(stored), null, false);
		}

		static ChunkAttempt failed(int userCount, String failureCode, boolean retryable) {
			return new ChunkAttempt(RecommendationBatchResult.empty().plusFailed(userCount), failureCode,
					retryable);
		}

		boolean succeeded() {
			return failureCode == null;
		}
	}

	/** 회차 안 묶음 하나. 재시도하면 마지막 시도 결과로 바뀐다. */
	private static final class Chunk {

		private final int no;
		private final List<Long> userIds;
		private ChunkAttempt last;
		private int attempts = 1;

		private Chunk(int no, List<Long> userIds, ChunkAttempt first) {
			this.no = no;
			this.userIds = userIds;
			this.last = first;
		}

		private void retry(ChunkAttempt next) {
			this.last = next;
			this.attempts++;
		}
	}
}

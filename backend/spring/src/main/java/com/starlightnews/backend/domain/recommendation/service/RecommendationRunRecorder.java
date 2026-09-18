package com.starlightnews.backend.domain.recommendation.service;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationCycleWindow;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationRun;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunChunk;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationRunChunkRepository;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationRunRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 추천 생성 회차의 실행 기록을 남긴다.
 *
 * <p>호출마다 따로 커밋한다. 회차는 트랜잭션 없이 돌므로, 도중에 서버가 내려가도 그때까지의
 * 기록은 남는다.
 */
@Service
@RequiredArgsConstructor
public class RecommendationRunRecorder {

	private final RecommendationRunRepository runRepository;
	private final RecommendationRunChunkRepository chunkRepository;

	/** 회차를 시작했다. 돌려준 ID 로 묶음과 종료를 기록한다. */
	@Transactional
	public Long start(RecommendationCycleWindow window, LocalDateTime startedAt) {
		return runRepository.save(RecommendationRun.start(window, startedAt)).getRunId();
	}

	@Transactional
	public void succeeded(Long runId, int chunkNo, List<Long> userIds) {
		chunkRepository.save(RecommendationRunChunk.succeeded(runId, chunkNo, userIds));
	}

	@Transactional
	public void failed(Long runId, int chunkNo, List<Long> userIds, String failureCode) {
		chunkRepository.save(RecommendationRunChunk.failed(runId, chunkNo, userIds, failureCode));
	}

	@Transactional
	public void finish(Long runId, int totalChunks, int failedChunks, int targetUsers,
			RecommendationBatchResult result, LocalDateTime finishedAt) {
		runRepository.findById(runId).ifPresent(run -> run.finish(totalChunks, failedChunks, targetUsers,
				result.storedUsers(), result.failedUsers(), finishedAt));
	}

	@Transactional
	public void abort(Long runId, LocalDateTime finishedAt) {
		runRepository.findById(runId).ifPresent(run -> run.abort(finishedAt));
	}
}

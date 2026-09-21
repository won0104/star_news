package com.starlightnews.backend.domain.article.analysis;

import java.time.LocalDateTime;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 기사 분석 회차의 실행 기록을 남긴다.
 *
 * <p>호출마다 따로 커밋한다. 회차는 트랜잭션 없이 돌므로, 도중에 서버가 내려가도 시작 기록은
 * 남는다. 추천 배치의 {@code RecommendationRunRecorder} 와 같은 방식이다.
 */
@Service
@RequiredArgsConstructor
public class ArticleAnalysisRunRecorder {

	private final ArticleAnalysisRunRepository runRepository;

	/** 회차를 시작했다. 돌려준 ID 로 종료를 기록한다. */
	@Transactional
	public Long start(int waitingBefore, LocalDateTime startedAt) {
		return runRepository.save(ArticleAnalysisRun.start(waitingBefore, startedAt)).getRunId();
	}

	@Transactional
	public void finish(Long runId, ArticleAnalysisBatchResult result, int remaining,
			Long oldestWaitMinutes, LocalDateTime finishedAt) {
		runRepository.findById(runId)
				.ifPresent(run -> run.finish(result, remaining, oldestWaitMinutes, finishedAt));
	}

	@Transactional
	public void abort(Long runId, LocalDateTime finishedAt) {
		runRepository.findById(runId).ifPresent(run -> run.abort(finishedAt));
	}
}

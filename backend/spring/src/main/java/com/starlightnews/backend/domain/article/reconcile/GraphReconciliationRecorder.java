package com.starlightnews.backend.domain.article.reconcile;

import java.time.LocalDateTime;
import java.util.List;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 대사 회차의 실행 기록과 찾은 어긋남을 남긴다.
 *
 * <p>호출마다 따로 커밋한다. 회차는 트랜잭션 없이 돌므로 도중에 서버가 내려가도 시작 기록은 남는다.
 * 분석 배치의 {@code ArticleAnalysisRunRecorder} 와 같은 방식이다.
 */
@Service
@RequiredArgsConstructor
public class GraphReconciliationRecorder {

	private final GraphReconciliationRunRepository runRepository;
	private final GraphReconciliationIssueRepository issueRepository;

	@Transactional
	public Long start(LocalDateTime startedAt) {
		return runRepository.save(GraphReconciliationRun.start(startedAt)).getRunId();
	}

	@Transactional
	public void saveIssues(Long runId, List<RecordedIssue> issues, LocalDateTime createdAt) {
		issueRepository.saveAll(issues.stream()
				.map(recorded -> new GraphReconciliationIssueRecord(runId, recorded.issue(), recorded.action(), createdAt))
				.toList());
	}

	@Transactional
	public void finish(Long runId, GraphReconciliationResult result, LocalDateTime finishedAt) {
		runRepository.findById(runId).ifPresent(run -> run.finish(result, finishedAt));
	}

	@Transactional
	public void abort(Long runId, LocalDateTime finishedAt) {
		runRepository.findById(runId).ifPresent(run -> run.abort(finishedAt));
	}

	/** 기록할 어긋남과 그에 대해 한 일. */
	public record RecordedIssue(ReconciliationIssue issue, ReconciliationAction action) {
	}
}

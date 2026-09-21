package com.starlightnews.backend.domain.article.analysis;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 기사 분석 회차 한 번의 실행 기록. ({@code article_analysis_runs})
 *
 * <p>시작할 때 {@link ArticleAnalysisRunStatus#RUNNING} 으로 넣고, 회차가 끝나면 결과로 상태를 정한다.
 */
@Entity
@Table(name = "article_analysis_runs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ArticleAnalysisRun {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "run_id")
	private Long runId;

	@Enumerated(EnumType.STRING)
	@Column(name = "status", nullable = false, length = 32)
	private ArticleAnalysisRunStatus status;

	/** 회차를 시작할 때 대기 중이던 기사 수. 회차 상한과 무관하게 센 값이다. */
	@Column(name = "waiting_before", nullable = false)
	private int waitingBefore;

	@Column(name = "processed", nullable = false)
	private int processed;

	@Column(name = "completed", nullable = false)
	private int completed;

	@Column(name = "dropped", nullable = false)
	private int dropped;

	@Column(name = "will_retry", nullable = false)
	private int willRetry;

	@Column(name = "gave_up", nullable = false)
	private int gaveUp;

	@Column(name = "errors", nullable = false)
	private int errors;

	/** 회차가 끝난 뒤 남은 대기 수. */
	@Column(name = "remaining", nullable = false)
	private int remaining;

	/** 남은 대기 중 가장 오래 기다린 기사가 수집된 지 몇 분인지. 대기가 없으면 비어 있다. */
	@Column(name = "oldest_wait_minutes")
	private Long oldestWaitMinutes;

	@Column(name = "started_at", nullable = false)
	private LocalDateTime startedAt;

	@Column(name = "finished_at")
	private LocalDateTime finishedAt;

	private ArticleAnalysisRun(int waitingBefore, LocalDateTime startedAt) {
		this.status = ArticleAnalysisRunStatus.RUNNING;
		this.waitingBefore = waitingBefore;
		this.startedAt = startedAt;
	}

	public static ArticleAnalysisRun start(int waitingBefore, LocalDateTime startedAt) {
		return new ArticleAnalysisRun(waitingBefore, startedAt);
	}

	/** 회차가 끝났다. 중간에 멈췄으면 그 이유가 상태가 된다. */
	public void finish(ArticleAnalysisBatchResult result, int remaining, Long oldestWaitMinutes,
			LocalDateTime finishedAt) {
		this.status = ArticleAnalysisRunStatus.of(result.stopReason());
		this.processed = result.processed();
		this.completed = result.completed();
		this.dropped = result.dropped();
		this.willRetry = result.willRetry();
		this.gaveUp = result.gaveUp();
		this.errors = result.errors();
		this.remaining = remaining;
		this.oldestWaitMinutes = oldestWaitMinutes;
		this.finishedAt = finishedAt;
	}

	/** 회차가 예외로 끊겼다. */
	public void abort(LocalDateTime finishedAt) {
		this.status = ArticleAnalysisRunStatus.ABORTED;
		this.finishedAt = finishedAt;
	}
}

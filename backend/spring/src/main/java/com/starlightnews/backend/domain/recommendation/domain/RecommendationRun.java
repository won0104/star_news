package com.starlightnews.backend.domain.recommendation.domain;

import java.time.LocalDateTime;

import com.starlightnews.backend.global.enums.RecommendationCycle;
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
 * 추천 생성 회차 한 번의 실행 기록. ({@code recommendation_runs})
 *
 * <p>시작할 때 {@link RecommendationRunStatus#RUNNING} 으로 넣고, 묶음을 다 돈 뒤 결과로 상태를 정한다.
 */
@Entity
@Table(name = "recommendation_runs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class RecommendationRun {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "run_id")
	private Long runId;

	@Enumerated(EnumType.STRING)
	@Column(name = "cycle", nullable = false, length = 8)
	private RecommendationCycle cycle;

	@Column(name = "available_at", nullable = false)
	private LocalDateTime availableAt;

	@Enumerated(EnumType.STRING)
	@Column(name = "status", nullable = false, length = 16)
	private RecommendationRunStatus status;

	@Column(name = "total_chunks", nullable = false)
	private int totalChunks;

	@Column(name = "failed_chunks", nullable = false)
	private int failedChunks;

	@Column(name = "target_users", nullable = false)
	private int targetUsers;

	@Column(name = "stored_users", nullable = false)
	private int storedUsers;

	@Column(name = "failed_users", nullable = false)
	private int failedUsers;

	@Column(name = "started_at", nullable = false)
	private LocalDateTime startedAt;

	@Column(name = "finished_at")
	private LocalDateTime finishedAt;

	private RecommendationRun(RecommendationCycleWindow window, LocalDateTime startedAt) {
		this.cycle = window.cycle();
		this.availableAt = window.availableAt();
		this.status = RecommendationRunStatus.RUNNING;
		this.startedAt = startedAt;
	}

	public static RecommendationRun start(RecommendationCycleWindow window, LocalDateTime startedAt) {
		return new RecommendationRun(window, startedAt);
	}

	/** 묶음을 다 돌았다. 실패한 묶음 수로 상태를 정한다. */
	public void finish(int totalChunks, int failedChunks, int targetUsers, int storedUsers, int failedUsers,
			LocalDateTime finishedAt) {
		this.status = RecommendationRunStatus.of(totalChunks, failedChunks);
		this.totalChunks = totalChunks;
		this.failedChunks = failedChunks;
		this.targetUsers = targetUsers;
		this.storedUsers = storedUsers;
		this.failedUsers = failedUsers;
		this.finishedAt = finishedAt;
	}

	/** 묶음을 다 돌기 전에 예외로 끊겼다. */
	public void abort(LocalDateTime finishedAt) {
		this.status = RecommendationRunStatus.FAILED;
		this.finishedAt = finishedAt;
	}
}

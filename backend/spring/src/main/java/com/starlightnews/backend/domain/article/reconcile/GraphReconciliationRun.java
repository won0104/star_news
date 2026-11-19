package com.starlightnews.backend.domain.article.reconcile;

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
 * 대사 회차 한 번의 실행 기록. ({@code graph_reconciliation_runs})
 */
@Entity
@Table(name = "graph_reconciliation_runs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class GraphReconciliationRun {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "run_id")
	private Long runId;

	@Enumerated(EnumType.STRING)
	@Column(name = "status", nullable = false, length = 32)
	private GraphReconciliationRunStatus status;

	@Column(name = "mysql_checked", nullable = false)
	private int mysqlChecked;

	@Column(name = "graph_checked", nullable = false)
	private int graphChecked;

	@Column(name = "missing_graph", nullable = false)
	private int missingGraph;

	@Column(name = "node_id_mismatch", nullable = false)
	private int nodeIdMismatch;

	@Column(name = "unreflected", nullable = false)
	private int unreflected;

	@Column(name = "orphan_graph", nullable = false)
	private int orphanGraph;

	@Column(name = "dropped_with_graph", nullable = false)
	private int droppedWithGraph;

	@Column(name = "requeued", nullable = false)
	private int requeued;

	@Column(name = "started_at", nullable = false)
	private LocalDateTime startedAt;

	@Column(name = "finished_at")
	private LocalDateTime finishedAt;

	private GraphReconciliationRun(LocalDateTime startedAt) {
		this.status = GraphReconciliationRunStatus.RUNNING;
		this.startedAt = startedAt;
	}

	public static GraphReconciliationRun start(LocalDateTime startedAt) {
		return new GraphReconciliationRun(startedAt);
	}

	public void finish(GraphReconciliationResult result, LocalDateTime finishedAt) {
		this.status = GraphReconciliationRunStatus.COMPLETED;
		this.mysqlChecked = result.mysqlChecked();
		this.graphChecked = result.graphChecked();
		this.missingGraph = result.missingGraph();
		this.nodeIdMismatch = result.nodeIdMismatch();
		this.unreflected = result.unreflected();
		this.droppedWithGraph = result.droppedWithGraph();
		this.orphanGraph = result.orphanGraph();
		this.requeued = result.requeued();
		this.finishedAt = finishedAt;
	}

	public void abort(LocalDateTime finishedAt) {
		this.status = GraphReconciliationRunStatus.ABORTED;
		this.finishedAt = finishedAt;
	}
}

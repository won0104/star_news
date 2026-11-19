package com.starlightnews.backend.domain.article.reconcile;

public enum GraphReconciliationRunStatus {
	RUNNING,
	COMPLETED,
	/** 조회 실패 등으로 회차가 끊겼다. */
	ABORTED
}

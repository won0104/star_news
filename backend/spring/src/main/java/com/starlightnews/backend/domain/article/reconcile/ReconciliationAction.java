package com.starlightnews.backend.domain.article.reconcile;

/** 어긋남을 찾고 한 일. */
public enum ReconciliationAction {

	/** 세고 기록만 했다. */
	REPORTED,

	/** 기사를 분석 대기로 되돌렸다. */
	REQUEUED
}

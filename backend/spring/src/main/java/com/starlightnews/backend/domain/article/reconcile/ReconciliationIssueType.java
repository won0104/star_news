package com.starlightnews.backend.domain.article.reconcile;

/**
 * MySQL 과 Neo4j 가 어긋난 모양.
 */
public enum ReconciliationIssueType {

	/** MySQL 은 COMPLETED 인데 그래프에 기사가 없다. 화면에서 기사는 보이는데 관련 사건이 비어 있게 된다. */
	MISSING_GRAPH(true),

	/** 양쪽에 다 있지만 노드 ID 가 다르다. MySQL 이 가리키는 노드로는 그래프를 찾지 못한다. */
	NODE_ID_MISMATCH(false),

	/**
	 * 그래프에는 기사가 들어갔는데 MySQL 은 FAILED 로 굳었다. FastAPI 는 끝까지 썼지만 응답이 유실됐거나
	 * Spring 이 반영하지 못한 경우다. 재요청이 다시 오지 않아 영영 FAILED 로 남는다.
	 */
	UNREFLECTED(true),

	/** AI 가 분석할 수 없다고 판단한(DROPPED) 기사가 그래프에 있다. 어느 쪽이 맞는지 사람이 봐야 한다. */
	DROPPED_WITH_GRAPH(false),

	/** 그래프에 기사가 있는데 MySQL 에는 행이 없다. 지울지 말지는 그래프의 쓰기 주체(FastAPI)가 정한다. */
	ORPHAN_GRAPH(false);

	private final boolean requeueable;

	ReconciliationIssueType(boolean requeueable) {
		this.requeueable = requeueable;
	}

	/** 기사를 다시 분석 대기로 돌리면 풀리는 어긋남인지. 나머지는 세고 기록만 한다. */
	public boolean requeueable() {
		return requeueable;
	}
}

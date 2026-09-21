package com.starlightnews.backend.domain.article.analysis;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisBatchResult.StopReason;

/**
 * 기사 분석 회차의 실행 상태.
 */
public enum ArticleAnalysisRunStatus {

	/** 돌고 있다. 서버가 도중에 내려가면 이 상태로 남는다. */
	RUNNING,

	/** 대기열을 끝까지 돌았다. 대기가 없어 아무것도 안 한 회차도 여기에 든다. */
	COMPLETED,

	/** 시간 예산을 다 써서 남은 기사를 다음 회차로 넘겼다. */
	OUT_OF_TIME,

	/** 연달아 실패해 멈췄다. AI 워커 장애로 본다. */
	TOO_MANY_FAILURES,

	/** 설정 오류로 멈췄다. 어느 기사를 불러도 실패한다. */
	HALTED,

	/** 회차가 예외로 끊겼다. */
	ABORTED;

	/** 끝난 회차의 상태를 정한다. 중간에 멈춘 이유가 없으면 완료다. */
	public static ArticleAnalysisRunStatus of(StopReason stopReason) {
		if (stopReason == null) {
			return COMPLETED;
		}
		return switch (stopReason) {
			case OUT_OF_TIME -> OUT_OF_TIME;
			case TOO_MANY_FAILURES -> TOO_MANY_FAILURES;
			case HALTED -> HALTED;
		};
	}
}

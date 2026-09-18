package com.starlightnews.backend.domain.article.analysis;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisRecorder.Recorded;

/**
 * 분석 회차 하나의 결과.
 *
 * @param completed  분석을 반영한 기사 수
 * @param dropped    분석할 수 없어 뺀 기사 수
 * @param willRetry  실패해서 다음 회차에 다시 시도할 기사 수
 * @param gaveUp     한도까지 실패해 더 시도하지 않을 기사 수
 * @param errors     반영하다 예상하지 못한 오류가 난 기사 수
 * @param stopReason 회차를 중간에 멈췄으면 그 이유. 끝까지 돌았으면 null
 */
public record ArticleAnalysisBatchResult(
		int completed,
		int dropped,
		int willRetry,
		int gaveUp,
		int errors,
		StopReason stopReason
) {

	public static ArticleAnalysisBatchResult empty() {
		return new ArticleAnalysisBatchResult(0, 0, 0, 0, 0, null);
	}

	public ArticleAnalysisBatchResult plus(Recorded recorded) {
		return switch (recorded) {
			case COMPLETED -> new ArticleAnalysisBatchResult(completed + 1, dropped, willRetry, gaveUp, errors, stopReason);
			case DROPPED -> new ArticleAnalysisBatchResult(completed, dropped + 1, willRetry, gaveUp, errors, stopReason);
			case WILL_RETRY -> new ArticleAnalysisBatchResult(completed, dropped, willRetry + 1, gaveUp, errors, stopReason);
			case GAVE_UP -> new ArticleAnalysisBatchResult(completed, dropped, willRetry, gaveUp + 1, errors, stopReason);
			case UNCHANGED -> this;
		};
	}

	public ArticleAnalysisBatchResult plusError() {
		return new ArticleAnalysisBatchResult(completed, dropped, willRetry, gaveUp, errors + 1, stopReason);
	}

	public ArticleAnalysisBatchResult stoppedBy(StopReason reason) {
		return new ArticleAnalysisBatchResult(completed, dropped, willRetry, gaveUp, errors, reason);
	}

	/** 처리한 기사 수. */
	public int processed() {
		return completed + dropped + willRetry + gaveUp + errors;
	}

	/** 회차를 중간에 멈춘 이유. */
	public enum StopReason {

		/** 설정 오류. 어느 기사를 불러도 실패한다. */
		HALTED,

		/** 연달아 실패했다. AI 워커 장애로 보고 더 태우지 않는다. */
		TOO_MANY_FAILURES,

		/** 시간 예산을 다 썼다. 남은 기사는 다음 회차로 넘긴다. */
		OUT_OF_TIME
	}
}

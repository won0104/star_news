package com.starlightnews.backend.domain.article.analysis;

import com.starlightnews.backend.domain.article.analysis.dto.ArticleAnalyzeResponse;

/**
 * 기사 한 건 분석의 결과. 호출자가 다음에 무엇을 할지로 나눈다.
 */
public sealed interface ArticleAnalysisOutcome {

	/** 분석됐다. 결과를 MySQL 에 반영한다. */
	record Analyzed(ArticleAnalyzeResponse.Data result) implements ArticleAnalysisOutcome {
	}

	/**
	 * 기사 내용이 분석할 수 없는 것이다. 다시 불러도 같다. 분석 대상에서 뺀다.
	 */
	record Rejected(String reason) implements ArticleAnalysisOutcome {
	}

	/**
	 * 일시적으로 실패했다. 다음 회차에 다시 시도한다.
	 */
	record Retryable(String reason) implements ArticleAnalysisOutcome {
	}

	/**
	 * 설정이 잘못돼 어느 기사를 불러도 실패한다. 회차를 멈춘다.
	 */
	record Halt(String reason) implements ArticleAnalysisOutcome {
	}
}

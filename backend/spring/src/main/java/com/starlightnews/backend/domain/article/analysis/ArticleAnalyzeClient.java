package com.starlightnews.backend.domain.article.analysis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Analyzed;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Halt;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Rejected;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Retryable;
import com.starlightnews.backend.domain.article.analysis.dto.ArticleAnalyzeRequest;
import com.starlightnews.backend.domain.article.analysis.dto.ArticleAnalyzeResponse;
import com.starlightnews.backend.global.client.FastApiClient;
import com.starlightnews.backend.global.client.FastApiProperties;
import com.starlightnews.backend.global.client.InternalApiErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

/**
 * 기사 한 건의 AI 분석을 FastAPI 에 요청한다.
 *
 * <p>FastAPI 는 AI 워커에 추론을 맡기고, 돌아온 그래프를 Neo4j 에 반영한 뒤 Article 의 nodeId 와
 * 분류를 돌려준다. 여기서는 그 결과를 받아 호출자가 다음에 할 일로 나눠 준다.
 *
 * <p>공용 {@link FastApiClient} 빈을 쓰지 않고 긴 타임아웃의 RestClient 로 따로 만든다. 헤더·에러
 * 매핑은 같은 코드를 그대로 쓴다.
 */
@Slf4j
@Component
public class ArticleAnalyzeClient {

	private static final String ANALYZE_PATH = "/internal/v1/articles/analyze";

	private final FastApiClient fastApiClient;

	public ArticleAnalyzeClient(@Qualifier("fastApiAnalysisRestClient") RestClient analysisRestClient,
			FastApiProperties fastApiProperties, ObjectMapper objectMapper) {
		this.fastApiClient = new FastApiClient(analysisRestClient, fastApiProperties, objectMapper);
	}

	/** 기사 한 건을 분석한다. 실패도 예외가 아니라 결과로 돌려준다. */
	public ArticleAnalysisOutcome analyze(ArticleAnalyzeRequest request) {
		ArticleAnalyzeResponse response;
		try {
			response = fastApiClient.post(ANALYZE_PATH, request, ArticleAnalyzeResponse.class);
		} catch (BusinessException failure) {
			return classify(failure.getErrorCode(), request.articleId());
		}

		if (!isComplete(response)) {
			// 200 인데 필요한 값이 없다. 그대로 반영하면 node_id 가 빈 COMPLETED 기사가 생긴다.
			log.warn("기사 분석 응답에 필요한 값이 없습니다. (articleId={})", request.articleId());
			return new Retryable("INCOMPLETE_RESPONSE");
		}
		return new Analyzed(response.data());
	}

	private ArticleAnalysisOutcome classify(ErrorCode errorCode, long articleId) {
		String code = errorCode.getCode();
		if (errorCode == InternalApiErrorCode.INTERNAL_API_REJECTED) {
			log.info("분석할 수 없는 기사입니다. (articleId={})", articleId);
			return new Rejected(code);
		}
		if (errorCode == InternalApiErrorCode.INTERNAL_API_UNAUTHORIZED) {
			// 키 문제다. 어느 기사를 불러도 같으니 회차를 멈춘다.
			return new Halt(code);
		}
		log.warn("기사 분석 실패, 다음 회차에 다시 시도합니다. (articleId={}, 원인={})", articleId, code);
		return new Retryable(code);
	}

	private boolean isComplete(ArticleAnalyzeResponse response) {
		if (response == null || response.data() == null) {
			return false;
		}
		ArticleAnalyzeResponse.Data data = response.data();
		return isPresent(data.articleNodeId()) && isPresent(data.primaryTopicCode());
	}

	private boolean isPresent(String value) {
		return value != null && !value.isBlank();
	}
}

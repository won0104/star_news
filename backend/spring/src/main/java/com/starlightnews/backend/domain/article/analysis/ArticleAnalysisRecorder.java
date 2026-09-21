package com.starlightnews.backend.domain.article.analysis;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Analyzed;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Halt;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Rejected;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Retryable;
import com.starlightnews.backend.domain.article.analysis.dto.ArticleAnalyzeResponse;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.TopicCode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 기사 한 건의 분석 결과를 MySQL 에 반영한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ArticleAnalysisRecorder {

	/** 분석은 됐는데 우리가 모르는 분류가 온 경우. 실패 원인으로 남긴다. */
	static final String UNKNOWN_TOPIC = "UNKNOWN_TOPIC";

	private final ArticleRepository articleRepository;
	private final ArticleAnalysisProperties properties;

	/**
	 * 분석 결과를 반영한다.
	 *
	 * @return 반영한 뒤 그 기사가 어떻게 됐는지
	 */
	@Transactional
	public Recorded record(long articleId, ArticleAnalysisOutcome outcome) {
		return switch (outcome) {
			case Analyzed analyzed -> recordAnalyzed(articleId, analyzed.result());
			case Rejected rejected -> recordRejected(articleId, rejected.reason());
			case Retryable retryable -> recordFailure(articleId, retryable.reason());
			// 기사 탓이 아니다. 시도 횟수를 올리면 설정을 고치는 사이 멀쩡한 기사가 FAILED 가 된다.
			case Halt halt -> Recorded.UNCHANGED;
		};
	}

	private Recorded recordAnalyzed(long articleId, ArticleAnalyzeResponse.Data result) {
		if (TopicCode.from(result.primaryTopicCode()).isEmpty()) {
			log.warn("알 수 없는 분류라 반영하지 않습니다. (articleId={}, topicCode={})",
					articleId, result.primaryTopicCode());
			return recordFailure(articleId, UNKNOWN_TOPIC);
		}

		int updated = articleRepository.markAnalyzed(articleId, result.articleNodeId(),
				result.primaryTopicCode(), result.subtopicCode());
		return updated == 0 ? Recorded.UNCHANGED : Recorded.COMPLETED;
	}

	private Recorded recordRejected(long articleId, String failureCode) {
		int updated = articleRepository.markAnalysisRejected(articleId, failureCode);
		return updated == 0 ? Recorded.UNCHANGED : Recorded.DROPPED;
	}

	private Recorded recordFailure(long articleId, String failureCode) {
		int updated = articleRepository.recordAnalysisFailure(articleId, properties.maxAttempts(),
				failureCode);
		if (updated == 0) {
			return Recorded.UNCHANGED;
		}

		boolean gaveUp = articleRepository.findAnalysisStatus(articleId)
				.filter(status -> status == AnalysisStatus.FAILED)
				.isPresent();
		if (gaveUp) {
			log.warn("분석을 {}번 실패해 더 시도하지 않습니다. (articleId={})", properties.maxAttempts(), articleId);
			return Recorded.GAVE_UP;
		}
		return Recorded.WILL_RETRY;
	}

	/** 반영한 뒤 기사의 처지. 회차 로그의 건수로 쓴다. */
	public enum Recorded {

		/** 분석 결과를 반영했다. */
		COMPLETED,

		/** 분석할 수 없는 기사라 대상에서 뺐다. */
		DROPPED,

		/** 실패했고 다음 회차에 다시 시도한다. */
		WILL_RETRY,

		/** 한도까지 실패해 더 시도하지 않는다. */
		GAVE_UP,

		/** 바꾼 것이 없다. 이미 분석 대기가 아니었거나 회차를 멈춘 경우다. */
		UNCHANGED
	}
}

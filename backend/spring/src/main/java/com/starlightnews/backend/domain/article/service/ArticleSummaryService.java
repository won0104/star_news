package com.starlightnews.backend.domain.article.service;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.starlightnews.backend.domain.article.dto.ArticleSummaryResponse;
import com.starlightnews.backend.domain.article.exception.ArticleErrorCode;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.repository.ArticleRepository.ArticleSummaryTarget;
import com.starlightnews.backend.global.client.GmsClient;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.SummaryStatus;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;

/** 최초 기사 상세 진입 시 필요한 기사 요약을 생성하고 저장한다. */
@Slf4j
@Service
@RequiredArgsConstructor
public class ArticleSummaryService {

	private static final int MAX_SUMMARY_CODE_POINTS = 200;
	private static final Pattern SENTENCE_END_PATTERN =
			Pattern.compile("(?<!\\d)[.!?](?!\\d)[\\\"'”’)]*(?=\\s|$)");
	private static final Pattern WHITESPACE_PATTERN = Pattern.compile("\\s+");
	private static final Pattern MISSING_SENTENCE_SPACE_PATTERN = Pattern.compile("([.!?])(?=[가-힣])");

	private static final String INSTRUCTION = """
			너는 뉴스 기사를 짧고 정확하게 요약하는 편집자다.
			주어진 기사 제목과 본문만 근거로 핵심 내용을 한국어로 요약하라.

			- 핵심 사건이나 결정을 먼저 제시하고, 주요 근거와 수치, 본문에 제시된 영향이나 전망을 중요도 순으로 충분히 담는다.
			- 핵심 정보가 적으면 짧게 작성해도 되며, 분량을 채우기 위해 내용을 반복하거나 추측하지 않는다.
			- 어떤 경우에도 공백과 문장부호를 포함해 200자를 초과하지 않는다.
			- 기사의 핵심을 객관적으로 전달하는 요약문으로 쓰고, 모든 문장을 "~했다", "~이다", "~전망이다"와 같은 하다체로 끝맺는다.
			- 키워드와 수치만 나열하는 개조식, 명사형 종결, 화살표나 괄호에 의존한 축약을 사용하지 않는다.
			- 각 문장에 주어와 서술어를 갖춘 2~3개의 자연스러운 완결 문장으로 작성한다.
			- 기사에 없는 내용을 추측하거나 추가하지 않는다.
			- 언론사 이름, 기자 이름, 기사 제목은 언급하지 않는다.
			- "이 기사는", "요약하면" 같은 말로 시작하지 않고 내용부터 바로 쓴다.
			- 요약문 외의 설명이나 형식 표시는 출력하지 않는다.""";

	private static final String REWRITE_INSTRUCTION = """
			너는 뉴스 요약문을 다듬는 편집자다.
			아래 요약문의 사실과 핵심 의미를 유지하면서 다시 작성하라.

			- 공백과 문장부호를 포함해 200자를 초과하지 않는다.
			- 내용을 새로 추가하거나 추측하지 않는다.
			- 모든 문장을 하다체의 자연스러운 완결 문장으로 작성한다.
			- 키워드와 수치만 나열하는 개조식을 사용하지 않는다.
			- 수정한 요약문 외의 설명이나 형식 표시는 출력하지 않는다.""";

	private final ArticleRepository articleRepository;
	private final ArticleSummaryWriter writer;
	private final GmsClient gmsClient;

	/** 저장된 요약을 재사용하고, 필요한 경우에만 GMS 로 새 요약을 만든다. */
	public ArticleSummaryResponse generate(Long articleId) {
		ArticleSummaryTarget target = findTarget(articleId);

		if (target.getSummaryStatus() == SummaryStatus.COMPLETED) {
			return completedResponse(target.getArticleId(), target.getSummary());
		}
		if (target.getSummaryStatus() == SummaryStatus.PROCESSING) {
			return processingResponse(target.getArticleId());
		}
		if (target.getContent() == null || target.getContent().isBlank()) {
			throw new BusinessException(ArticleErrorCode.ARTICLE_CONTENT_UNAVAILABLE);
		}

		if (!claim(articleId)) {
			return responseAfterLostClaim(articleId);
		}

		String summary = generateWithGms(target);
		saveSummary(articleId, summary);
		return completedResponse(articleId, summary);
	}

	private ArticleSummaryTarget findTarget(Long articleId) {
		try {
			return articleRepository.findSummaryTargetByArticleIdAndAnalysisStatus(
					articleId, AnalysisStatus.COMPLETED)
					.orElseThrow(() -> new BusinessException(ArticleErrorCode.ARTICLE_NOT_FOUND));
		} catch (DataAccessException exception) {
			log.error("기사 요약 대상 조회에 실패했습니다. articleId={}", articleId, exception);
			throw new BusinessException(ArticleErrorCode.ARTICLE_DETAIL_QUERY_FAILED);
		}
	}

	private boolean claim(Long articleId) {
		try {
			return writer.claim(articleId);
		} catch (DataAccessException exception) {
			log.error("기사 요약 생성 상태 선점에 실패했습니다. articleId={}", articleId, exception);
			throw new BusinessException(ArticleErrorCode.SUMMARY_SAVE_FAILED);
		}
	}

	private ArticleSummaryResponse responseAfterLostClaim(Long articleId) {
		ArticleSummaryTarget current = findTarget(articleId);
		return switch (current.getSummaryStatus()) {
			case COMPLETED -> completedResponse(articleId, current.getSummary());
			case PROCESSING -> processingResponse(articleId);
			case FAILED -> throw new BusinessException(ArticleErrorCode.SUMMARY_GENERATION_FAILED);
			case NOT_REQUESTED -> throw new BusinessException(ArticleErrorCode.SUMMARY_SAVE_FAILED);
		};
	}

	private String generateWithGms(ArticleSummaryTarget target) {
		String input = "기사 제목: %s%n%n[기사 본문]%n%s"
				.formatted(target.getTitle(), target.getContent());
		try {
			String summary = normalizeSummary(gmsClient.generate(INSTRUCTION, input));
			if (codePointCount(summary) <= MAX_SUMMARY_CODE_POINTS && endsWithCompleteSentence(summary)) {
				return summary;
			}

			String rewritten = normalizeSummary(gmsClient.generate(REWRITE_INSTRUCTION, summary));
			return keepCompleteSentencesWithinLimit(rewritten);
		} catch (RuntimeException exception) {
			markFailedOrThrow(target.getArticleId());
			log.warn("기사 요약 생성에 실패했습니다. articleId={}", target.getArticleId(), exception);
			throw new BusinessException(ArticleErrorCode.SUMMARY_GENERATION_FAILED);
		}
	}

	private void saveSummary(Long articleId, String summary) {
		try {
			writer.complete(articleId, summary);
		} catch (RuntimeException exception) {
			markFailedBestEffort(articleId);
			log.error("생성한 기사 요약 저장에 실패했습니다. articleId={}", articleId, exception);
			throw new BusinessException(ArticleErrorCode.SUMMARY_SAVE_FAILED);
		}
	}

	private void markFailedOrThrow(Long articleId) {
		try {
			writer.fail(articleId);
		} catch (RuntimeException exception) {
			log.error("기사 요약 실패 상태 저장에 실패했습니다. articleId={}", articleId, exception);
			throw new BusinessException(ArticleErrorCode.SUMMARY_SAVE_FAILED);
		}
	}

	private void markFailedBestEffort(Long articleId) {
		try {
			writer.fail(articleId);
		} catch (RuntimeException markFailure) {
			log.error("기사 요약 저장 실패 후 FAILED 상태 반영에도 실패했습니다. articleId={}",
					articleId, markFailure);
		}
	}

	private ArticleSummaryResponse completedResponse(Long articleId, String summary) {
		return new ArticleSummaryResponse(articleId, summary, SummaryStatus.COMPLETED);
	}

	private ArticleSummaryResponse processingResponse(Long articleId) {
		return new ArticleSummaryResponse(articleId, null, SummaryStatus.PROCESSING);
	}

	private static String normalizeSummary(String summary) {
		String normalizedWhitespace = WHITESPACE_PATTERN.matcher(summary.strip()).replaceAll(" ");
		return MISSING_SENTENCE_SPACE_PATTERN.matcher(normalizedWhitespace).replaceAll("$1 ");
	}

	private static int codePointCount(String value) {
		return value.codePointCount(0, value.length());
	}

	private static boolean endsWithCompleteSentence(String summary) {
		Matcher sentenceEnd = SENTENCE_END_PATTERN.matcher(summary);
		int lastSentenceEndIndex = -1;
		while (sentenceEnd.find()) {
			lastSentenceEndIndex = sentenceEnd.end();
		}
		return lastSentenceEndIndex == summary.length();
	}

	/** 200자를 넘긴 재작성 결과는 마지막 완결 문장까지만 남겨 문장 중간 절단을 막는다. */
	static String keepCompleteSentencesWithinLimit(String summary) {
		if (codePointCount(summary) <= MAX_SUMMARY_CODE_POINTS) {
			if (endsWithCompleteSentence(summary)) {
				return summary;
			}
			throw new IllegalStateException("완결된 요약 문장이 아닙니다.");
		}

		int maxEndIndex = summary.offsetByCodePoints(0, MAX_SUMMARY_CODE_POINTS);
		Matcher sentenceEnd = SENTENCE_END_PATTERN.matcher(summary);
		int lastCompleteEndIndex = -1;
		while (sentenceEnd.find() && sentenceEnd.end() <= maxEndIndex) {
			lastCompleteEndIndex = sentenceEnd.end();
		}
		if (lastCompleteEndIndex < 0) {
			throw new IllegalStateException("200자 이내에 완결된 요약 문장이 없습니다.");
		}
		return summary.substring(0, lastCompleteEndIndex).stripTrailing();
	}
}

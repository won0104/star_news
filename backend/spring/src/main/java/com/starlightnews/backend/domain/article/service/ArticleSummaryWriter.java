package com.starlightnews.backend.domain.article.service;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.exception.ArticleErrorCode;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.SummaryStatus;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/**
 * 기사 요약 상태를 짧은 개별 트랜잭션으로 변경한다.
 * GMS 호출 중에는 DB 트랜잭션을 열어두지 않는다.
 */
@Component
@RequiredArgsConstructor
public class ArticleSummaryWriter {

	private static final List<SummaryStatus> CLAIMABLE_STATUSES =
			List.of(SummaryStatus.NOT_REQUESTED, SummaryStatus.FAILED);

	private final ArticleRepository articleRepository;

	/** 동시에 들어온 요청 중 하나만 PROCESSING 상태를 선점한다. */
	@Transactional
	public boolean claim(Long articleId) {
		return articleRepository.claimSummaryGeneration(
				articleId,
				AnalysisStatus.COMPLETED,
				SummaryStatus.PROCESSING,
				CLAIMABLE_STATUSES) == 1;
	}

	/** 생성된 요약을 PROCESSING 상태에만 저장한다. */
	@Transactional
	public void complete(Long articleId, String summary) {
		int updated = articleRepository.completeSummaryGeneration(
				articleId,
				summary,
				LocalDateTime.now(),
				SummaryStatus.PROCESSING,
				SummaryStatus.COMPLETED);
		if (updated != 1) {
			throw new BusinessException(ArticleErrorCode.SUMMARY_SAVE_FAILED);
		}
	}

	/** 생성에 실패한 PROCESSING 상태를 FAILED 로 바꾼다. */
	@Transactional
	public void fail(Long articleId) {
		int updated = articleRepository.failSummaryGeneration(
				articleId, SummaryStatus.PROCESSING, SummaryStatus.FAILED);
		if (updated != 1) {
			throw new BusinessException(ArticleErrorCode.SUMMARY_SAVE_FAILED);
		}
	}
}

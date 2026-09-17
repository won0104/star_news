package com.starlightnews.backend.domain.article.service;

import java.util.List;

import com.starlightnews.backend.domain.article.exception.ArticleErrorCode;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.SummaryStatus;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class ArticleSummaryWriterTest {

	private static final Long ARTICLE_ID = 101L;

	@Mock
	private ArticleRepository articleRepository;

	@InjectMocks
	private ArticleSummaryWriter writer;

	@Test
	void 생성_가능한_상태를_PROCESSING으로_선점한다() {
		given(articleRepository.claimSummaryGeneration(
				ARTICLE_ID,
				AnalysisStatus.COMPLETED,
				SummaryStatus.PROCESSING,
				List.of(SummaryStatus.NOT_REQUESTED, SummaryStatus.FAILED)))
				.willReturn(1);

		assertThat(writer.claim(ARTICLE_ID)).isTrue();
	}

	@Test
	void 완료_저장_대상이_PROCESSING이_아니면_SUMMARY_SAVE_FAILED_예외다() {
		given(articleRepository.completeSummaryGeneration(
				org.mockito.ArgumentMatchers.eq(ARTICLE_ID),
				org.mockito.ArgumentMatchers.eq("생성된 요약"),
				org.mockito.ArgumentMatchers.any(),
				org.mockito.ArgumentMatchers.eq(SummaryStatus.PROCESSING),
				org.mockito.ArgumentMatchers.eq(SummaryStatus.COMPLETED)))
				.willReturn(0);

		Throwable thrown = catchThrowable(() -> writer.complete(ARTICLE_ID, "생성된 요약"));

		assertThat(thrown).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) thrown).getErrorCode())
				.isEqualTo(ArticleErrorCode.SUMMARY_SAVE_FAILED);
	}

	@Test
	void 실패_상태를_저장한다() {
		given(articleRepository.failSummaryGeneration(
				ARTICLE_ID, SummaryStatus.PROCESSING, SummaryStatus.FAILED)).willReturn(1);

		writer.fail(ARTICLE_ID);

		verify(articleRepository).failSummaryGeneration(
				ARTICLE_ID, SummaryStatus.PROCESSING, SummaryStatus.FAILED);
	}

	@Test
	void 실패_상태_저장_대상이_PROCESSING이_아니면_SUMMARY_SAVE_FAILED_예외다() {
		given(articleRepository.failSummaryGeneration(
				ARTICLE_ID, SummaryStatus.PROCESSING, SummaryStatus.FAILED)).willReturn(0);

		Throwable thrown = catchThrowable(() -> writer.fail(ARTICLE_ID));

		assertThat(thrown).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) thrown).getErrorCode())
				.isEqualTo(ArticleErrorCode.SUMMARY_SAVE_FAILED);
	}
}

package com.starlightnews.backend.domain.article.service;

import java.util.Optional;

import com.starlightnews.backend.domain.article.dto.ArticleSummaryResponse;
import com.starlightnews.backend.domain.article.exception.ArticleErrorCode;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.repository.ArticleRepository.ArticleSummaryTarget;
import com.starlightnews.backend.global.client.GmsClient;
import com.starlightnews.backend.global.client.GmsErrorCode;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.SummaryStatus;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataAccessResourceFailureException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class ArticleSummaryServiceTest {

	private static final Long ARTICLE_ID = 101L;
	private static final String TITLE = "국방부, 한미 연합훈련 일정 발표";
	private static final String CONTENT = "국방부가 한미 연합훈련 일정을 발표하고 세부 훈련 계획을 공개했다.";

	@Mock
	private ArticleRepository articleRepository;

	@Mock
	private ArticleSummaryWriter writer;

	@Mock
	private GmsClient gmsClient;

	@InjectMocks
	private ArticleSummaryService articleSummaryService;

	@Test
	void COMPLETED면_GMS를_호출하지_않고_저장된_요약을_반환한다() {
		givenTarget(target(SummaryStatus.COMPLETED, "기존 요약", CONTENT));

		ArticleSummaryResponse response = articleSummaryService.generate(ARTICLE_ID);

		assertThat(response.summary()).isEqualTo("기존 요약");
		assertThat(response.summaryStatus()).isEqualTo(SummaryStatus.COMPLETED);
		verifyNoInteractions(writer, gmsClient);
	}

	@Test
	void PROCESSING이면_GMS를_호출하지_않고_현재_상태를_반환한다() {
		givenTarget(target(SummaryStatus.PROCESSING, null, CONTENT));

		ArticleSummaryResponse response = articleSummaryService.generate(ARTICLE_ID);

		assertThat(response.summary()).isNull();
		assertThat(response.summaryStatus()).isEqualTo(SummaryStatus.PROCESSING);
		verifyNoInteractions(writer, gmsClient);
	}

	@Test
	void NOT_REQUESTED를_선점한_요청만_GMS_요약을_저장한다() {
		givenTarget(target(SummaryStatus.NOT_REQUESTED, null, CONTENT));
		given(writer.claim(ARTICLE_ID)).willReturn(true);
		given(gmsClient.generate(anyString(), anyString())).willReturn(" 생성된 기사 요약이다. ");

		ArticleSummaryResponse response = articleSummaryService.generate(ARTICLE_ID);

		assertThat(response.summary()).isEqualTo("생성된 기사 요약이다.");
		assertThat(response.summaryStatus()).isEqualTo(SummaryStatus.COMPLETED);
		verify(writer).complete(ARTICLE_ID, "생성된 기사 요약이다.");

		ArgumentCaptor<String> instruction = ArgumentCaptor.forClass(String.class);
		ArgumentCaptor<String> input = ArgumentCaptor.forClass(String.class);
		verify(gmsClient).generate(instruction.capture(), input.capture());
		assertThat(instruction.getValue())
				.contains("200자를 초과하지 않는다")
				.contains("하다체로 끝맺는다")
				.contains("개조식");
		assertThat(input.getValue()).contains(TITLE, CONTENT);
	}

	@Test
	void FAILED도_다시_선점해_요약을_생성한다() {
		givenTarget(target(SummaryStatus.FAILED, null, CONTENT));
		given(writer.claim(ARTICLE_ID)).willReturn(true);
		given(gmsClient.generate(anyString(), anyString())).willReturn("재시도 요약이다.");

		ArticleSummaryResponse response = articleSummaryService.generate(ARTICLE_ID);

		assertThat(response.summary()).isEqualTo("재시도 요약이다.");
		verify(writer).claim(ARTICLE_ID);
		verify(writer).complete(ARTICLE_ID, "재시도 요약이다.");
	}

	@Test
	void 선점하지_못하고_다른_요청이_처리중이면_PROCESSING을_반환한다() {
		given(articleRepository.findSummaryTargetByArticleIdAndAnalysisStatus(
				ARTICLE_ID, AnalysisStatus.COMPLETED))
				.willReturn(
						Optional.of(target(SummaryStatus.NOT_REQUESTED, null, CONTENT)),
						Optional.of(target(SummaryStatus.PROCESSING, null, CONTENT)));
		given(writer.claim(ARTICLE_ID)).willReturn(false);

		ArticleSummaryResponse response = articleSummaryService.generate(ARTICLE_ID);

		assertThat(response.summaryStatus()).isEqualTo(SummaryStatus.PROCESSING);
		verifyNoInteractions(gmsClient);
	}

	@Test
	void 본문이_없으면_ARTICLE_CONTENT_UNAVAILABLE_예외다() {
		givenTarget(target(SummaryStatus.NOT_REQUESTED, null, "   "));

		Throwable thrown = catchThrowable(() -> articleSummaryService.generate(ARTICLE_ID));

		assertErrorCode(thrown, ArticleErrorCode.ARTICLE_CONTENT_UNAVAILABLE);
		verifyNoInteractions(writer, gmsClient);
	}

	@Test
	void 분석_완료_기사를_찾을_수_없으면_ARTICLE_NOT_FOUND_예외다() {
		given(articleRepository.findSummaryTargetByArticleIdAndAnalysisStatus(
				ARTICLE_ID, AnalysisStatus.COMPLETED)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> articleSummaryService.generate(ARTICLE_ID));

		assertErrorCode(thrown, ArticleErrorCode.ARTICLE_NOT_FOUND);
		verifyNoInteractions(writer, gmsClient);
	}

	@Test
	void GMS_실패는_FAILED로_기록하고_SUMMARY_GENERATION_FAILED로_변환한다() {
		givenTarget(target(SummaryStatus.NOT_REQUESTED, null, CONTENT));
		given(writer.claim(ARTICLE_ID)).willReturn(true);
		given(gmsClient.generate(anyString(), anyString()))
				.willThrow(new BusinessException(GmsErrorCode.GMS_UNAVAILABLE));

		Throwable thrown = catchThrowable(() -> articleSummaryService.generate(ARTICLE_ID));

		assertErrorCode(thrown, ArticleErrorCode.SUMMARY_GENERATION_FAILED);
		verify(writer).fail(ARTICLE_ID);
		verify(writer, never()).complete(org.mockito.ArgumentMatchers.anyLong(), anyString());
	}

	@Test
	void 예상하지_못한_GMS_처리_실패도_FAILED로_기록한다() {
		givenTarget(target(SummaryStatus.NOT_REQUESTED, null, CONTENT));
		given(writer.claim(ARTICLE_ID)).willReturn(true);
		given(gmsClient.generate(anyString(), anyString()))
				.willThrow(new IllegalStateException("unexpected response"));

		Throwable thrown = catchThrowable(() -> articleSummaryService.generate(ARTICLE_ID));

		assertErrorCode(thrown, ArticleErrorCode.SUMMARY_GENERATION_FAILED);
		verify(writer).fail(ARTICLE_ID);
	}

	@Test
	void 요약_저장_실패는_FAILED로_변경하고_SUMMARY_SAVE_FAILED를_응답한다() {
		givenTarget(target(SummaryStatus.NOT_REQUESTED, null, CONTENT));
		given(writer.claim(ARTICLE_ID)).willReturn(true);
		given(gmsClient.generate(anyString(), anyString())).willReturn("생성된 요약이다.");
		org.mockito.Mockito.doThrow(new DataAccessResourceFailureException("database unavailable"))
				.when(writer).complete(ARTICLE_ID, "생성된 요약이다.");

		Throwable thrown = catchThrowable(() -> articleSummaryService.generate(ARTICLE_ID));

		assertErrorCode(thrown, ArticleErrorCode.SUMMARY_SAVE_FAILED);
		verify(writer).fail(ARTICLE_ID);
	}

	@Test
	void GMS_결과가_200자를_초과하면_한_번_재작성한다() {
		givenTarget(target(SummaryStatus.NOT_REQUESTED, null, CONTENT));
		given(writer.claim(ARTICLE_ID)).willReturn(true);
		String tooLong = "첫 문장이다. " + "가".repeat(200);
		String rewritten = "핵심 내용을 유지한 완결된 요약문이다.";
		given(gmsClient.generate(anyString(), anyString())).willReturn(tooLong, rewritten);

		ArticleSummaryResponse response = articleSummaryService.generate(ARTICLE_ID);

		assertThat(response.summary()).isEqualTo(rewritten);
		verify(gmsClient, times(2)).generate(anyString(), anyString());
		verify(writer).complete(ARTICLE_ID, rewritten);
	}

	@Test
	void 재작성_결과도_200자를_초과하면_마지막_완결_문장까지만_남긴다() {
		String source = "첫 번째 완결 문장이다. " + "가".repeat(200) + ".";

		String limited = ArticleSummaryService.keepCompleteSentencesWithinLimit(source);

		assertThat(limited).isEqualTo("첫 번째 완결 문장이다.");
		assertThat(limited.codePointCount(0, limited.length())).isLessThanOrEqualTo(200);
	}

	@Test
	void 소수점은_문장_끝으로_판단하지_않는다() {
		String source = "첫 번째 완결 문장이다. " + "가".repeat(170)
				+ " 나스닥은 1.79% 하락했다고 발표했다.";

		String limited = ArticleSummaryService.keepCompleteSentencesWithinLimit(source);

		assertThat(source.codePointCount(0, source.length())).isGreaterThan(200);
		assertThat(limited).isEqualTo("첫 번째 완결 문장이다.");
	}

	private void givenTarget(ArticleSummaryTarget target) {
		given(articleRepository.findSummaryTargetByArticleIdAndAnalysisStatus(
				ARTICLE_ID, AnalysisStatus.COMPLETED)).willReturn(Optional.of(target));
	}

	private ArticleSummaryTarget target(SummaryStatus status, String summary, String content) {
		return new ArticleSummaryTarget() {
			@Override
			public Long getArticleId() {
				return ARTICLE_ID;
			}

			@Override
			public String getTitle() {
				return TITLE;
			}

			@Override
			public String getContent() {
				return content;
			}

			@Override
			public String getSummary() {
				return summary;
			}

			@Override
			public SummaryStatus getSummaryStatus() {
				return status;
			}
		};
	}

	private void assertErrorCode(Throwable thrown, ArticleErrorCode expected) {
		assertThat(thrown).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) thrown).getErrorCode()).isEqualTo(expected);
	}
}

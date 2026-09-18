package com.starlightnews.backend.domain.article.analysis;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.LongStream;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisBatchResult.StopReason;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Analyzed;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Halt;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Rejected;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Retryable;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisRecorder.Recorded;
import com.starlightnews.backend.domain.article.analysis.dto.ArticleAnalyzeRequest;
import com.starlightnews.backend.domain.article.analysis.dto.ArticleAnalyzeResponse;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.repository.ArticleRepository.AnalysisTarget;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Limit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class ArticleAnalysisBatchServiceTest {

	@Mock
	private ArticleRepository articleRepository;

	@Mock
	private ArticleAnalyzeClient analyzeClient;

	@Mock
	private ArticleAnalysisRecorder recorder;

	private ArticleAnalysisBatchService service;

	@BeforeEach
	void setUp() {
		service = service(Duration.ofMinutes(30));
	}

	/** 시도 3회, 회차당 300건, 연속 실패 5건에서 중단 */
	private ArticleAnalysisBatchService service(Duration timeBudget) {
		return new ArticleAnalysisBatchService(articleRepository, analyzeClient, recorder,
				new ArticleAnalysisProperties(Duration.ofSeconds(180), 300, 3, timeBudget, 5));
	}

	private AnalysisTarget target(long articleId) {
		return new AnalysisTarget() {
			public Long getArticleId() { return articleId; }
			public String getTitle() { return "제목 " + articleId; }
			public String getContent() { return "본문"; }
			public Long getOrganizationId() { return 940010L; }
			public String getOrganizationName() { return "연합뉴스"; }
			public LocalDateTime getPublishedAt() { return LocalDateTime.of(2026, 9, 16, 9, 30); }
		};
	}

	private void givenQueue(long count) {
		given(articleRepository.findAnalysisQueue(eq(3), any(Limit.class)))
				.willReturn(LongStream.rangeClosed(1, count).mapToObj(this::target).toList());
	}

	private Analyzed analyzed() {
		return new Analyzed(new ArticleAnalyzeResponse.Data(1L, "node", "COMPLETED", "ECONOMY", "ECONOMY_FINANCE"));
	}

	@Test
	void 대기_중인_기사가_없으면_아무것도_부르지_않는다() {
		givenQueue(0);

		assertThat(service.analyzePending()).isEqualTo(ArticleAnalysisBatchResult.empty());
		verify(analyzeClient, never()).analyze(any());
	}

	@Test
	void 대기열을_설정한_한도와_개수로_고른다() {
		givenQueue(0);

		service.analyzePending();

		ArgumentCaptor<Limit> limit = ArgumentCaptor.forClass(Limit.class);
		verify(articleRepository).findAnalysisQueue(eq(3), limit.capture());
		assertThat(limit.getValue().max()).isEqualTo(300);
	}

	@Test
	void 기사를_하나씩_분석하고_결과를_반영한다() {
		givenQueue(3);
		given(analyzeClient.analyze(any())).willReturn(analyzed());
		given(recorder.record(anyLong(), any())).willReturn(Recorded.COMPLETED);

		ArticleAnalysisBatchResult result = service.analyzePending();

		assertThat(result.completed()).isEqualTo(3);
		assertThat(result.stopReason()).isNull();
		verify(recorder).record(eq(1L), any());
		verify(recorder).record(eq(2L), any());
		verify(recorder).record(eq(3L), any());
	}

	@Test
	void 기사_정보를_요청에_옮겨_담는다() {
		givenQueue(1);
		given(analyzeClient.analyze(any())).willReturn(analyzed());
		given(recorder.record(anyLong(), any())).willReturn(Recorded.COMPLETED);

		service.analyzePending();

		ArgumentCaptor<ArticleAnalyzeRequest> request = ArgumentCaptor.forClass(ArticleAnalyzeRequest.class);
		verify(analyzeClient).analyze(request.capture());
		assertThat(request.getValue().articleId()).isEqualTo(1L);
		assertThat(request.getValue().sourceId()).isEqualTo(940010L);
		assertThat(request.getValue().sourceName()).isEqualTo("연합뉴스");
		assertThat(request.getValue().publishedAt().getOffset().getTotalSeconds()).isEqualTo(9 * 3600);
	}

	@Test
	void 결과별로_건수를_센다() {
		givenQueue(4);
		given(analyzeClient.analyze(any())).willReturn(analyzed());
		given(recorder.record(anyLong(), any()))
				.willReturn(Recorded.COMPLETED, Recorded.DROPPED, Recorded.WILL_RETRY, Recorded.GAVE_UP);

		ArticleAnalysisBatchResult result = service.analyzePending();

		assertThat(result.completed()).isEqualTo(1);
		assertThat(result.dropped()).isEqualTo(1);
		assertThat(result.willRetry()).isEqualTo(1);
		assertThat(result.gaveUp()).isEqualTo(1);
	}

	@Test
	void 설정_오류면_바로_멈추고_기사를_건드리지_않는다() {
		// 계속 부르면 기사마다 시도 횟수만 올라 멀쩡한 기사가 FAILED 가 된다.
		givenQueue(3);
		given(analyzeClient.analyze(any())).willReturn(new Halt("INTERNAL_API_UNAUTHORIZED"));

		ArticleAnalysisBatchResult result = service.analyzePending();

		assertThat(result.stopReason()).isEqualTo(StopReason.HALTED);
		verify(analyzeClient, times(1)).analyze(any());
		verify(recorder, never()).record(anyLong(), any());
	}

	@Test
	void 연속으로_실패하면_AI_워커_장애로_보고_멈춘다() {
		// 장애 몇 시간 사이에 수백 건이 시도 횟수를 다 써 FAILED 가 되는 것을 막는다.
		givenQueue(20);
		given(analyzeClient.analyze(any())).willReturn(new Retryable("INTERNAL_API_UNAVAILABLE"));
		given(recorder.record(anyLong(), any())).willReturn(Recorded.WILL_RETRY);

		ArticleAnalysisBatchResult result = service.analyzePending();

		assertThat(result.stopReason()).isEqualTo(StopReason.TOO_MANY_FAILURES);
		assertThat(result.willRetry()).isEqualTo(5);
		verify(analyzeClient, times(5)).analyze(any());
	}

	@Test
	void 사이에_성공이_끼면_연속_실패를_처음부터_센다() {
		// 드문드문 실패하는 건 기사 탓일 수 있다. 장애는 연달아 실패한다.
		givenQueue(9);
		Retryable failed = new Retryable("EXTRACTION_FAILED");
		given(analyzeClient.analyze(any()))
				.willReturn(failed, failed, failed, failed, analyzed(), failed, failed, failed, failed);
		given(recorder.record(anyLong(), any())).willReturn(Recorded.WILL_RETRY);

		ArticleAnalysisBatchResult result = service.analyzePending();

		assertThat(result.stopReason()).isNull();
		verify(analyzeClient, times(9)).analyze(any());
	}

	@Test
	void 분석할_수_없는_기사는_연속_실패로_세지_않는다() {
		// 기사 내용 문제라 AI 워커가 멀쩡하다는 뜻이다.
		givenQueue(8);
		given(analyzeClient.analyze(any())).willReturn(new Rejected("INTERNAL_API_REJECTED"));
		given(recorder.record(anyLong(), any())).willReturn(Recorded.DROPPED);

		ArticleAnalysisBatchResult result = service.analyzePending();

		assertThat(result.stopReason()).isNull();
		assertThat(result.dropped()).isEqualTo(8);
	}

	@Test
	void 시간_예산을_다_쓰면_새_기사를_시작하지_않는다() {
		givenQueue(3);

		ArticleAnalysisBatchResult result = service(Duration.ZERO).analyzePending();

		assertThat(result.stopReason()).isEqualTo(StopReason.OUT_OF_TIME);
		verify(analyzeClient, never()).analyze(any());
	}

	@Test
	void 반영하다_오류가_나도_다음_기사로_넘어간다() {
		// 기사 한 건 때문에 회차가 통째로 죽지 않게 한다.
		givenQueue(3);
		given(analyzeClient.analyze(any())).willReturn(analyzed());
		given(recorder.record(anyLong(), any()))
				.willThrow(new IllegalStateException("DB 오류"))
				.willReturn(Recorded.COMPLETED, Recorded.COMPLETED);

		ArticleAnalysisBatchResult result = service.analyzePending();

		assertThat(result.errors()).isEqualTo(1);
		assertThat(result.completed()).isEqualTo(2);
	}

	@Test
	void 예상하지_못한_오류도_연속되면_멈춘다() {
		givenQueue(10);
		given(analyzeClient.analyze(any())).willThrow(new IllegalStateException("알 수 없는 오류"));

		ArticleAnalysisBatchResult result = service.analyzePending();

		assertThat(result.stopReason()).isEqualTo(StopReason.TOO_MANY_FAILURES);
		assertThat(result.errors()).isEqualTo(5);
	}

	@Test
	void 회차_전후로_남은_대기를_센다() {
		// 처리량이 유입을 못 따라가는지 로그로 보려면 회차 상한이 아닌 전체 대기가 필요하다.
		givenQueue(1);
		given(analyzeClient.analyze(any())).willReturn(analyzed());
		given(recorder.record(anyLong(), any())).willReturn(Recorded.COMPLETED);
		given(articleRepository.countAnalysisQueue(3)).willReturn(10L, 9L);
		given(articleRepository.findOldestAnalysisWaitMinutes(3)).willReturn(312L);

		service.analyzePending();

		verify(articleRepository, times(2)).countAnalysisQueue(3);
		verify(articleRepository).findOldestAnalysisWaitMinutes(3);
	}

	@Test
	void 남은_대기가_없으면_오래_기다린_시간을_묻지_않는다() {
		givenQueue(1);
		given(analyzeClient.analyze(any())).willReturn(analyzed());
		given(recorder.record(anyLong(), any())).willReturn(Recorded.COMPLETED);
		given(articleRepository.countAnalysisQueue(3)).willReturn(1L, 0L);

		service.analyzePending();

		verify(articleRepository, never()).findOldestAnalysisWaitMinutes(anyInt());
	}

	@Test
	void 회차가_끝까지_돌면_중단_이유가_없다() {
		givenQueue(2);
		given(analyzeClient.analyze(any())).willReturn(analyzed());
		given(recorder.record(anyLong(), any())).willReturn(Recorded.COMPLETED);

		assertThat(service.analyzePending().stopReason()).isNull();
	}

	@Test
	void 기사_목록을_주어진_차례대로_부른다() {
		givenQueue(3);
		given(analyzeClient.analyze(any())).willReturn(analyzed());
		given(recorder.record(anyLong(), any())).willReturn(Recorded.COMPLETED);

		service.analyzePending();

		ArgumentCaptor<ArticleAnalyzeRequest> requests = ArgumentCaptor.forClass(ArticleAnalyzeRequest.class);
		verify(analyzeClient, times(3)).analyze(requests.capture());
		assertThat(requests.getAllValues()).extracting(ArticleAnalyzeRequest::articleId)
				.isEqualTo(List.of(1L, 2L, 3L));
	}
}

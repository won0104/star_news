package com.starlightnews.backend.domain.article.analysis;

import java.time.LocalDateTime;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisBatchResult.StopReason;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 분석 회차 기록을 실제 MySQL 에서 확인한다.
 *
 * <p>로그는 컨테이너를 다시 띄우면 사라진다. 며칠치 처리량과 밀린 정도를 보려면 DB 에 남아야 한다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class ArticleAnalysisRunRecorderTest {

	private static final LocalDateTime STARTED_AT = LocalDateTime.of(2026, 9, 21, 12, 20);
	private static final LocalDateTime FINISHED_AT = LocalDateTime.of(2026, 9, 21, 12, 34);

	@Autowired
	private ArticleAnalysisRunRecorder recorder;

	@Autowired
	private ArticleAnalysisRunRepository runRepository;

	@Autowired
	private EntityManager entityManager;

	private ArticleAnalysisRun reload(Long runId) {
		entityManager.flush();
		entityManager.clear();
		return runRepository.findById(runId).orElseThrow();
	}

	@Test
	void 회차를_시작하면_도는_중으로_남는다() {
		Long runId = recorder.start(20, STARTED_AT);

		ArticleAnalysisRun run = reload(runId);
		assertThat(run.getStatus()).isEqualTo(ArticleAnalysisRunStatus.RUNNING);
		assertThat(run.getWaitingBefore()).isEqualTo(20);
		assertThat(run.getStartedAt()).isEqualTo(STARTED_AT);
		assertThat(run.getFinishedAt()).isNull();
	}

	@Test
	void 끝까지_돈_회차는_건수와_함께_완료로_남는다() {
		Long runId = recorder.start(20, STARTED_AT);

		recorder.finish(runId, new ArticleAnalysisBatchResult(17, 1, 1, 1, 0, null), 2, 86L, FINISHED_AT);

		ArticleAnalysisRun run = reload(runId);
		assertThat(run.getStatus()).isEqualTo(ArticleAnalysisRunStatus.COMPLETED);
		assertThat(run.getProcessed()).isEqualTo(20);
		assertThat(run.getCompleted()).isEqualTo(17);
		assertThat(run.getDropped()).isEqualTo(1);
		assertThat(run.getWillRetry()).isEqualTo(1);
		assertThat(run.getGaveUp()).isEqualTo(1);
		assertThat(run.getRemaining()).isEqualTo(2);
		assertThat(run.getOldestWaitMinutes()).isEqualTo(86L);
		assertThat(run.getFinishedAt()).isEqualTo(FINISHED_AT);
	}

	@Test
	void 시간_예산을_다_쓴_회차는_그_이유가_상태로_남는다() {
		// 이 상태가 잦아지면 예산이나 수집량을 조정해야 한다는 신호다.
		Long runId = recorder.start(50, STARTED_AT);

		recorder.finish(runId, ArticleAnalysisBatchResult.empty().stoppedBy(StopReason.OUT_OF_TIME),
				30, 120L, FINISHED_AT);

		assertThat(reload(runId).getStatus()).isEqualTo(ArticleAnalysisRunStatus.OUT_OF_TIME);
	}

	@Test
	void 연속_실패로_멈춘_회차도_구분된다() {
		Long runId = recorder.start(10, STARTED_AT);

		recorder.finish(runId, ArticleAnalysisBatchResult.empty().stoppedBy(StopReason.TOO_MANY_FAILURES),
				10, 30L, FINISHED_AT);

		assertThat(reload(runId).getStatus()).isEqualTo(ArticleAnalysisRunStatus.TOO_MANY_FAILURES);
	}

	@Test
	void 대기가_없으면_최장_대기_시간은_비어_있다() {
		Long runId = recorder.start(0, STARTED_AT);

		recorder.finish(runId, ArticleAnalysisBatchResult.empty(), 0, null, FINISHED_AT);

		ArticleAnalysisRun run = reload(runId);
		assertThat(run.getStatus()).isEqualTo(ArticleAnalysisRunStatus.COMPLETED);
		assertThat(run.getOldestWaitMinutes()).isNull();
	}

	@Test
	void 예외로_끊긴_회차는_중단으로_남는다() {
		Long runId = recorder.start(20, STARTED_AT);

		recorder.abort(runId, FINISHED_AT);

		ArticleAnalysisRun run = reload(runId);
		assertThat(run.getStatus()).isEqualTo(ArticleAnalysisRunStatus.ABORTED);
		assertThat(run.getFinishedAt()).isEqualTo(FINISHED_AT);
	}
}

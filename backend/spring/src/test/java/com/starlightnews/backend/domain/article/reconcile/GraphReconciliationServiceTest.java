package com.starlightnews.backend.domain.article.reconcile;

import java.util.Collection;
import java.util.List;

import com.starlightnews.backend.domain.article.reconcile.GraphReconciliationRecorder.RecordedIssue;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.repository.ArticleRepository.ArticleNodeRef;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Limit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class GraphReconciliationServiceTest {

	private static final Long RUN_ID = 7L;

	@Mock
	private ArticleRepository articleRepository;

	@Mock
	private GraphArticleRepository graphArticleRepository;

	@Mock
	private GraphReconciliationRepair repair;

	@Mock
	private GraphReconciliationRecorder recorder;

	private GraphReconciliationService service(int pageSize, boolean requeue, int maxStored) {
		return new GraphReconciliationService(articleRepository, graphArticleRepository, repair, recorder,
				new GraphReconciliationProperties(true, pageSize, requeue, maxStored));
	}

	private static ArticleNodeRef ref(long id, AnalysisStatus status, String nodeId) {
		return new ArticleNodeRef() {
			@Override
			public Long getArticleId() {
				return id;
			}

			@Override
			public String getNodeId() {
				return nodeId;
			}

			@Override
			public AnalysisStatus getAnalysisStatus() {
				return status;
			}
		};
	}

	/**
	 * MySQL COMPLETED 3건(1·2·3) 중 2 는 그래프에 없고 3 은 노드 ID 가 다르다.
	 * 그래프 Article 3건(1·3·4) 중 4 는 MySQL 에서 FAILED 다.
	 * 페이지 크기 2 라 양쪽 모두 두 페이지에 걸쳐 읽는다.
	 */
	private void givenTwoPagesEachSide() {
		given(articleRepository.findCompletedNodeRefsAfter(eq(0L), any(Limit.class)))
				.willReturn(List.of(ref(1, AnalysisStatus.COMPLETED, "n-1"), ref(2, AnalysisStatus.COMPLETED, "n-2")));
		given(articleRepository.findCompletedNodeRefsAfter(eq(2L), any(Limit.class)))
				.willReturn(List.of(ref(3, AnalysisStatus.COMPLETED, "n-3")));
		given(graphArticleRepository.findByMysqlArticleIds(List.of(1L, 2L)))
				.willReturn(List.of(new GraphArticleRef(1, "n-1")));
		given(graphArticleRepository.findByMysqlArticleIds(List.of(3L)))
				.willReturn(List.of(new GraphArticleRef(3, "n-x")));

		given(graphArticleRepository.findPageAfter(0L, 2))
				.willReturn(List.of(new GraphArticleRef(1, "n-1"), new GraphArticleRef(3, "n-x")));
		given(graphArticleRepository.findPageAfter(3L, 2))
				.willReturn(List.of(new GraphArticleRef(4, "n-4")));
		given(articleRepository.findNodeRefsByArticleIdIn(List.of(1L, 3L)))
				.willReturn(List.of(ref(1, AnalysisStatus.COMPLETED, "n-1"), ref(3, AnalysisStatus.COMPLETED, "n-3")));
		given(articleRepository.findNodeRefsByArticleIdIn(List.of(4L)))
				.willReturn(List.of(ref(4, AnalysisStatus.FAILED, null)));

		given(recorder.start(any())).willReturn(RUN_ID);
	}

	@SuppressWarnings("unchecked")
	private List<RecordedIssue> storedIssues() {
		ArgumentCaptor<List<RecordedIssue>> captor = ArgumentCaptor.forClass(List.class);
		verify(recorder).saveIssues(eq(RUN_ID), captor.capture(), any());
		return captor.getValue();
	}

	@Test
	void 양쪽을_페이지_단위로_끝까지_읽고_어긋남을_센다() {
		givenTwoPagesEachSide();

		GraphReconciliationResult result = service(2, false, 100).reconcile();

		assertThat(result.mysqlChecked()).isEqualTo(3);
		assertThat(result.graphChecked()).isEqualTo(3);
		assertThat(result.missingGraph()).isEqualTo(1);
		assertThat(result.nodeIdMismatch()).isEqualTo(1);
		assertThat(result.unreflected()).isEqualTo(1);
		assertThat(result.issues()).isEqualTo(3);
		verify(recorder).finish(eq(RUN_ID), eq(result), any());
	}

	@Test
	void 되돌리기를_끄면_세고_기록만_한다() {
		givenTwoPagesEachSide();

		GraphReconciliationResult result = service(2, false, 100).reconcile();

		assertThat(result.requeued()).isZero();
		verify(repair, never()).requeue(any());
		assertThat(storedIssues()).extracting(RecordedIssue::action)
				.containsOnly(ReconciliationAction.REPORTED);
	}

	@Test
	void 되돌리기를_켜면_다시_분석하면_풀리는_것만_되돌린다() {
		givenTwoPagesEachSide();
		given(repair.requeue(any())).willReturn(true);

		GraphReconciliationResult result = service(2, true, 100).reconcile();

		// 그래프 누락(2)과 반영 누락(4)만 되돌린다. 노드 ID 불일치(3)는 기록만 한다.
		assertThat(result.requeued()).isEqualTo(2);
		assertThat(storedIssues())
				.extracting(recorded -> recorded.issue().articleId(), RecordedIssue::action)
				.containsExactly(
						org.assertj.core.groups.Tuple.tuple(2L, ReconciliationAction.REQUEUED),
						org.assertj.core.groups.Tuple.tuple(3L, ReconciliationAction.REPORTED),
						org.assertj.core.groups.Tuple.tuple(4L, ReconciliationAction.REQUEUED));
	}

	@Test
	void 그사이_상태가_바뀌어_되돌리지_못하면_되돌린_수에_넣지_않는다() {
		givenTwoPagesEachSide();
		given(repair.requeue(any())).willReturn(false);

		GraphReconciliationResult result = service(2, true, 100).reconcile();

		assertThat(result.requeued()).isZero();
		assertThat(storedIssues()).extracting(RecordedIssue::action)
				.containsOnly(ReconciliationAction.REPORTED);
	}

	@Test
	void 상세는_상한까지만_남기고_건수는_모두_센다() {
		givenTwoPagesEachSide();

		GraphReconciliationResult result = service(2, false, 1).reconcile();

		assertThat(result.issues()).isEqualTo(3);
		assertThat(storedIssues()).hasSize(1);
	}

	@Test
	void 조회가_실패하면_기록을_중단으로_닫고_예외를_올려보낸다() {
		given(recorder.start(any())).willReturn(RUN_ID);
		given(articleRepository.findCompletedNodeRefsAfter(anyLong(), any(Limit.class)))
				.willReturn(List.of(ref(1, AnalysisStatus.COMPLETED, "n-1")));
		given(graphArticleRepository.findByMysqlArticleIds(anyCollection()))
				.willThrow(new IllegalStateException("Neo4j 연결 실패"));

		assertThatThrownBy(() -> service(2, false, 100).reconcile())
				.isInstanceOf(IllegalStateException.class);
		verify(recorder).abort(eq(RUN_ID), any());
		verify(recorder, never()).finish(any(), any(), any());
	}

	@Test
	void 기사가_없어도_회차는_완료로_남는다() {
		given(recorder.start(any())).willReturn(RUN_ID);
		given(articleRepository.findCompletedNodeRefsAfter(anyLong(), any(Limit.class))).willReturn(List.of());
		given(graphArticleRepository.findPageAfter(anyLong(), anyInt())).willReturn(List.of());

		GraphReconciliationResult result = service(2, false, 100).reconcile();

		assertThat(result.issues()).isZero();
		verify(recorder).finish(eq(RUN_ID), eq(result), any());
		verify(articleRepository, never()).findNodeRefsByArticleIdIn(any(Collection.class));
	}
}

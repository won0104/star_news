package com.starlightnews.backend.domain.article.reconcile;

import java.util.List;
import java.util.Map;

import com.starlightnews.backend.global.enums.AnalysisStatus;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class GraphReconcilerTest {

	private static MysqlArticleState completed(long id, String nodeId) {
		return new MysqlArticleState(id, AnalysisStatus.COMPLETED, nodeId);
	}

	@Test
	void 그래프와_노드_ID가_같으면_어긋나지_않았다() {
		var issues = GraphReconciler.compareCompleted(List.of(completed(1, "n-1")),
				Map.of(1L, new GraphArticleRef(1, "n-1")));

		assertThat(issues).isEmpty();
	}

	@Test
	void COMPLETED인데_그래프에_없으면_그래프_누락이다() {
		var issues = GraphReconciler.compareCompleted(List.of(completed(1, "n-1")), Map.of());

		assertThat(issues).singleElement().satisfies(issue -> {
			assertThat(issue.type()).isEqualTo(ReconciliationIssueType.MISSING_GRAPH);
			assertThat(issue.articleId()).isEqualTo(1);
			assertThat(issue.mysqlNodeId()).isEqualTo("n-1");
			assertThat(issue.graphNodeId()).isNull();
		});
	}

	@Test
	void 노드_ID가_다르면_불일치다() {
		var issues = GraphReconciler.compareCompleted(List.of(completed(1, "n-1")),
				Map.of(1L, new GraphArticleRef(1, "n-9")));

		assertThat(issues).singleElement().satisfies(issue -> {
			assertThat(issue.type()).isEqualTo(ReconciliationIssueType.NODE_ID_MISMATCH);
			assertThat(issue.graphNodeId()).isEqualTo("n-9");
		});
	}

	@Test
	void 그래프에만_있는_기사는_MySQL_상태에_따라_나눈다() {
		List<GraphArticleRef> page = List.of(
				new GraphArticleRef(1, "n-1"),   // MySQL 에 행이 없다
				new GraphArticleRef(2, "n-2"),   // FAILED 로 굳었다
				new GraphArticleRef(3, "n-3"),   // DROPPED 인데 그래프에 있다
				new GraphArticleRef(4, "n-4"),   // 분석 중이다
				new GraphArticleRef(5, "n-5"));  // COMPLETED 는 MySQL 쪽 비교가 이미 봤다
		Map<Long, MysqlArticleState> mysql = Map.of(
				2L, new MysqlArticleState(2, AnalysisStatus.FAILED, null),
				3L, new MysqlArticleState(3, AnalysisStatus.DROPPED, null),
				4L, new MysqlArticleState(4, AnalysisStatus.PROCESSING, null),
				5L, completed(5, "n-5"));

		var issues = GraphReconciler.compareGraphPage(page, mysql);

		assertThat(issues).extracting(ReconciliationIssue::articleId, ReconciliationIssue::type)
				.containsExactly(
						org.assertj.core.groups.Tuple.tuple(1L, ReconciliationIssueType.ORPHAN_GRAPH),
						org.assertj.core.groups.Tuple.tuple(2L, ReconciliationIssueType.UNREFLECTED),
						org.assertj.core.groups.Tuple.tuple(3L, ReconciliationIssueType.DROPPED_WITH_GRAPH));
	}

	@Test
	void 다시_분석하면_풀리는_어긋남만_되돌릴_수_있다() {
		assertThat(ReconciliationIssueType.MISSING_GRAPH.requeueable()).isTrue();
		assertThat(ReconciliationIssueType.UNREFLECTED.requeueable()).isTrue();
		assertThat(ReconciliationIssueType.NODE_ID_MISMATCH.requeueable()).isFalse();
		assertThat(ReconciliationIssueType.DROPPED_WITH_GRAPH.requeueable()).isFalse();
		assertThat(ReconciliationIssueType.ORPHAN_GRAPH.requeueable()).isFalse();
	}
}

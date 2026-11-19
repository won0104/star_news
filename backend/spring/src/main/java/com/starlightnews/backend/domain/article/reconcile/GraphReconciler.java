package com.starlightnews.backend.domain.article.reconcile;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * MySQL 과 Neo4j 를 맞대 어긋남을 고른다. 조회와 기록은 하지 않는 순수 비교다.
 *
 * <p>두 방향으로 본다. MySQL 이 COMPLETED 라고 한 기사가 그래프에 있는지({@link #compareCompleted}),
 * 그래프에 있는 기사를 MySQL 이 어떻게 알고 있는지({@link #compareGraphPage}). 한쪽에서만 보면
 * 그쪽에 없는 기사는 영영 보이지 않는다.
 */
public final class GraphReconciler {

	private GraphReconciler() {
	}

	/**
	 * MySQL 의 COMPLETED 기사 한 묶음을 그래프와 맞댄다.
	 *
	 * @param completed MySQL 에서 COMPLETED 인 기사
	 * @param graphById 같은 articleId 로 그래프에서 찾은 Article 노드
	 */
	public static List<ReconciliationIssue> compareCompleted(List<MysqlArticleState> completed,
			Map<Long, GraphArticleRef> graphById) {
		List<ReconciliationIssue> issues = new ArrayList<>();
		for (MysqlArticleState article : completed) {
			GraphArticleRef graph = graphById.get(article.articleId());
			if (graph == null) {
				issues.add(issue(ReconciliationIssueType.MISSING_GRAPH, article, null));
			} else if (!Objects.equals(article.nodeId(), graph.nodeId())) {
				issues.add(issue(ReconciliationIssueType.NODE_ID_MISMATCH, article, graph.nodeId()));
			}
		}
		return issues;
	}

	/**
	 * 그래프의 Article 한 페이지를 MySQL 과 맞댄다.
	 *
	 * <p>COMPLETED 는 {@link #compareCompleted} 가 이미 봤으므로 넘긴다. PROCESSING 도 넘긴다. 지금
	 * 분석 중인 기사이거나, 대기열에 있어 다음 회차가 재요청하면 FastAPI 가 그래프의 완료 결과를 돌려줘
	 * 저절로 맞춰진다. 대사가 끼어들 이유가 없다.
	 *
	 * @param page      그래프에서 읽은 Article 노드
	 * @param mysqlById 같은 articleId 의 MySQL 상태. 행이 없으면 빠진다
	 */
	public static List<ReconciliationIssue> compareGraphPage(List<GraphArticleRef> page,
			Map<Long, MysqlArticleState> mysqlById) {
		List<ReconciliationIssue> issues = new ArrayList<>();
		for (GraphArticleRef graph : page) {
			MysqlArticleState article = mysqlById.get(graph.mysqlArticleId());
			if (article == null) {
				issues.add(new ReconciliationIssue(ReconciliationIssueType.ORPHAN_GRAPH,
						graph.mysqlArticleId(), null, null, graph.nodeId()));
				continue;
			}
			switch (article.status()) {
				case FAILED -> issues.add(issue(ReconciliationIssueType.UNREFLECTED, article, graph.nodeId()));
				case DROPPED -> issues.add(issue(ReconciliationIssueType.DROPPED_WITH_GRAPH, article, graph.nodeId()));
				case COMPLETED, PROCESSING -> {
					// 위 주석 참고
				}
			}
		}
		return issues;
	}

	private static ReconciliationIssue issue(ReconciliationIssueType type, MysqlArticleState article,
			String graphNodeId) {
		return new ReconciliationIssue(type, article.articleId(), article.status(), article.nodeId(), graphNodeId);
	}
}

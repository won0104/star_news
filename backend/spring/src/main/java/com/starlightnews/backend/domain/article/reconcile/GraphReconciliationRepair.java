package com.starlightnews.backend.domain.article.reconcile;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 다시 분석하면 풀리는 어긋남을 분석 대기로 되돌린다. MySQL 만 고친다(Neo4j 의 쓰기 주체는 FastAPI).
 *
 * <p>대사가 본 상태 그대로일 때만 바꾼다. 비교와 수정 사이에 분석 배치가 상태를 바꿨으면 그쪽이
 * 최신이므로 건드리지 않는다.
 */
@Service
@RequiredArgsConstructor
public class GraphReconciliationRepair {

	static final String FAILURE_CODE_PREFIX = "RECONCILE_";

	private final ArticleRepository articleRepository;

	/**
	 * @return 되돌렸으면 true. 되돌릴 수 없는 종류이거나 그사이 상태가 바뀌었으면 false
	 */
	@Transactional
	public boolean requeue(ReconciliationIssue issue) {
		AnalysisStatus expected = switch (issue.type()) {
			case MISSING_GRAPH -> AnalysisStatus.COMPLETED;
			case UNREFLECTED -> AnalysisStatus.FAILED;
			case NODE_ID_MISMATCH, DROPPED_WITH_GRAPH, ORPHAN_GRAPH -> null;
		};
		if (expected == null) {
			return false;
		}
		return articleRepository.requeueForAnalysis(issue.articleId(), expected,
				FAILURE_CODE_PREFIX + issue.type().name()) > 0;
	}
}

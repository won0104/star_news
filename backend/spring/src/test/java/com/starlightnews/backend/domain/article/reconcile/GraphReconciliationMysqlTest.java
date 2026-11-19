package com.starlightnews.backend.domain.article.reconcile;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.reconcile.GraphReconciliationRecorder.RecordedIssue;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.repository.ArticleRepository.ArticleNodeRef;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.domain.Limit;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 대사가 쓰는 MySQL 조회 · 되돌리기 · 기록을 실제 MySQL 에서 확인한다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class GraphReconciliationMysqlTest {

	private static final long ORGANIZATION_ID = 93_100L;
	private static final LocalDateTime NOW = LocalDateTime.of(2026, 11, 20, 3, 40);

	@Autowired
	private ArticleRepository articleRepository;

	@Autowired
	private GraphReconciliationRepair repair;

	@Autowired
	private GraphReconciliationRecorder recorder;

	@Autowired
	private GraphReconciliationRunRepository runRepository;

	@Autowired
	private GraphReconciliationIssueRepository issueRepository;

	@Autowired
	private EntityManager entityManager;

	@BeforeEach
	void organization() {
		entityManager.createNativeQuery("INSERT INTO news_organizations (organization_id, name, domain) "
						+ "VALUES (?1, '연합뉴스', 'yna.co.kr') "
						+ "ON DUPLICATE KEY UPDATE organization_id = organization_id")
				.setParameter(1, ORGANIZATION_ID).executeUpdate();
	}

	private long insert(String key, String status, String nodeId, int attempts) {
		String url = "https://yna.co.kr/reconcile/" + key;
		entityManager.createNativeQuery("INSERT INTO articles "
						+ "(organization_id, title, url, url_hash, published_at, content, content_type, "
						+ " analysis_status, node_id, analysis_attempts) "
						+ "VALUES (?1, ?2, ?3, UNHEX(SHA2(?3, 256)), '2026-11-19 09:30:00', '본문', "
						+ " 'FULL_TEXT', ?4, ?5, ?6)")
				.setParameter(1, ORGANIZATION_ID).setParameter(2, "기사 " + key).setParameter(3, url)
				.setParameter(4, status).setParameter(5, nodeId).setParameter(6, attempts)
				.executeUpdate();
		entityManager.flush();
		return ((Number) entityManager.createNativeQuery("SELECT article_id FROM articles WHERE url = ?1")
				.setParameter(1, url).getSingleResult()).longValue();
	}

	private Object[] row(long articleId) {
		entityManager.flush();
		entityManager.clear();
		return (Object[]) entityManager.createNativeQuery("SELECT analysis_status, node_id, analysis_attempts, "
						+ "analysis_failure_code FROM articles WHERE article_id = ?1")
				.setParameter(1, articleId).getSingleResult();
	}

	@Test
	void COMPLETED만_ID_순으로_다음_페이지를_읽는다() {
		long first = insert("c1", "COMPLETED", "11111111-1111-1111-1111-111111111111", 0);
		insert("p1", "PROCESSING", null, 0);
		long second = insert("c2", "COMPLETED", "22222222-2222-2222-2222-222222222222", 0);

		List<Long> ids = articleRepository.findCompletedNodeRefsAfter(first - 1, Limit.of(10)).stream()
				.map(ArticleNodeRef::getArticleId).filter(id -> id >= first).toList();

		assertThat(ids).containsExactly(first, second);
	}

	@Test
	void 그래프_누락은_노드를_비우고_분석_대기로_되돌린다() {
		long articleId = insert("missing", "COMPLETED", "33333333-3333-3333-3333-333333333333", 2);

		boolean requeued = repair.requeue(new ReconciliationIssue(ReconciliationIssueType.MISSING_GRAPH,
				articleId, AnalysisStatus.COMPLETED, "33333333-3333-3333-3333-333333333333", null));

		assertThat(requeued).isTrue();
		Object[] row = row(articleId);
		assertThat(row[0]).isEqualTo("PROCESSING");
		assertThat(row[1]).isNull();
		assertThat(((Number) row[2]).intValue()).isZero();
		assertThat(row[3]).isEqualTo("RECONCILE_MISSING_GRAPH");
	}

	@Test
	void 대사가_본_상태와_다르면_되돌리지_않는다() {
		// 대사는 FAILED 로 봤지만 그사이 분석 배치가 다시 PROCESSING 으로 바꿨다.
		long articleId = insert("moved", "PROCESSING", null, 1);

		boolean requeued = repair.requeue(new ReconciliationIssue(ReconciliationIssueType.UNREFLECTED,
				articleId, AnalysisStatus.FAILED, null, "n-1"));

		assertThat(requeued).isFalse();
		assertThat(((Number) row(articleId)[2]).intValue()).isEqualTo(1);
	}

	@Test
	void 회차_기록과_어긋남_상세가_남는다() {
		Long runId = recorder.start(NOW);
		ReconciliationIssue issue = new ReconciliationIssue(ReconciliationIssueType.NODE_ID_MISMATCH, 42L,
				AnalysisStatus.COMPLETED, "44444444-4444-4444-4444-444444444444", "n-other");

		recorder.saveIssues(runId, List.of(new RecordedIssue(issue, ReconciliationAction.REPORTED)), NOW);
		recorder.finish(runId, new GraphReconciliationResult(10, 9, 0, 1, 0, 0, 0, 0), NOW.plusMinutes(1));
		entityManager.flush();
		entityManager.clear();

		GraphReconciliationRun run = runRepository.findById(runId).orElseThrow();
		assertThat(run.getStatus()).isEqualTo(GraphReconciliationRunStatus.COMPLETED);
		assertThat(run.getMysqlChecked()).isEqualTo(10);
		assertThat(run.getNodeIdMismatch()).isEqualTo(1);
		assertThat(issueRepository.findByRunIdOrderByIssueIdAsc(runId)).singleElement().satisfies(saved -> {
			assertThat(saved.getIssueType()).isEqualTo(ReconciliationIssueType.NODE_ID_MISMATCH);
			assertThat(saved.getGraphNodeId()).isEqualTo("n-other");
			assertThat(saved.getAction()).isEqualTo(ReconciliationAction.REPORTED);
		});
	}
}

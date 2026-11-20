package com.starlightnews.backend.domain.article.reconcile;

import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.article.reconcile.GraphReconciliationRecorder.RecordedIssue;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.repository.ArticleRepository.ArticleNodeRef;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Limit;
import org.springframework.stereotype.Service;

/**
 * MySQL 기사 분석 상태와 Neo4j Article 노드를 전수 대사한다.
 *
 * <p>두 저장소는 분산 트랜잭션으로 묶지 않는다. 분석 응답이 유실되면 다음 재요청 때 그래프의 완료
 * 결과를 재사용해 복구하지만, 재요청이 다시 오지 않는 어긋남은 아무도 모른 채 남는다. 이 배치가
 * 그것을 찾아 세고, 다시 분석하면 풀리는 것은 (설정을 켰을 때) 분석 대기로 되돌린다.
 *
 * <p>두 방향으로 읽는다. MySQL 의 COMPLETED 를 페이지 단위로 읽어 그래프에서 찾고, 그래프의 Article 을
 * 페이지 단위로 읽어 MySQL 에서 찾는다. 양쪽 모두 마지막 ID 다음부터 읽어 기사가 늘어도 뒤 페이지가
 * 느려지지 않는다.
 *
 * <p>Neo4j 에는 쓰지 않는다. 그래프 쪽에서만 고칠 수 있는 어긋남(고아 노드 등)은 기록만 하고 판단은
 * 그래프의 쓰기 주체(FastAPI)에 맡긴다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class GraphReconciliationService {

	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

	private final ArticleRepository articleRepository;
	private final GraphArticleRepository graphArticleRepository;
	private final GraphReconciliationRepair repair;
	private final GraphReconciliationRecorder recorder;
	private final GraphReconciliationProperties properties;
	private final GraphReconciliationMonitor monitor;

	public GraphReconciliationResult reconcile() {
		Long runId = recorder.start(LocalDateTime.now(SEOUL));
		try {
			Tally tally = new Tally(properties.maxStoredIssues());
			compareFromMysql(tally);
			compareFromGraph(tally);

			GraphReconciliationResult result = tally.result();
			recorder.saveIssues(runId, tally.stored, LocalDateTime.now(SEOUL));
			recorder.finish(runId, result, LocalDateTime.now(SEOUL));
			log.info("그래프 대사 종료: MySQL {}건 · 그래프 {}건 확인, 어긋남 {}건 (그래프 누락 {}, 노드 ID 불일치 {}, "
							+ "반영 누락 {}, 제외 후 그래프 존재 {}, 고아 노드 {}), 분석 대기로 되돌림 {}건",
					result.mysqlChecked(), result.graphChecked(), result.issues(), result.missingGraph(),
					result.nodeIdMismatch(), result.unreflected(), result.droppedWithGraph(), result.orphanGraph(),
					result.requeued());
			monitor.finished(result);
			return result;
		} catch (RuntimeException failure) {
			// 기록을 RUNNING 으로 두면 끝난 회차인지 도는 중인지 알 수 없다. 기록만 닫고 예외는 올려보낸다.
			// 삼키면 스케줄러는 성공으로 알고 아무도 알아차리지 못한다.
			recorder.abort(runId, LocalDateTime.now(SEOUL));
			log.error("그래프 대사 회차 중단", failure);
			monitor.aborted(failure);
			throw failure;
		}
	}

	/** MySQL 이 COMPLETED 라고 한 기사가 그래프에 그대로 있는지 본다. */
	private void compareFromMysql(Tally tally) {
		long afterId = 0;
		while (true) {
			List<ArticleNodeRef> page = articleRepository.findCompletedNodeRefsAfter(afterId,
					Limit.of(properties.pageSize()));
			if (page.isEmpty()) {
				return;
			}
			List<MysqlArticleState> completed = page.stream().map(GraphReconciliationService::toState).toList();
			Map<Long, GraphArticleRef> graphById = graphArticleRepository
					.findByMysqlArticleIds(completed.stream().map(MysqlArticleState::articleId).toList())
					.stream()
					.collect(Collectors.toMap(GraphArticleRef::mysqlArticleId, Function.identity(), (a, b) -> a));

			tally.mysqlChecked += completed.size();
			GraphReconciler.compareCompleted(completed, graphById).forEach(issue -> handle(issue, tally));

			afterId = completed.get(completed.size() - 1).articleId();
			if (page.size() < properties.pageSize()) {
				return;
			}
		}
	}

	/** 그래프에 있는 기사를 MySQL 이 어떻게 알고 있는지 본다. */
	private void compareFromGraph(Tally tally) {
		long afterId = 0;
		while (true) {
			List<GraphArticleRef> page = graphArticleRepository.findPageAfter(afterId, properties.pageSize());
			if (page.isEmpty()) {
				return;
			}
			Map<Long, MysqlArticleState> mysqlById = articleRepository
					.findNodeRefsByArticleIdIn(page.stream().map(GraphArticleRef::mysqlArticleId).toList())
					.stream()
					.map(GraphReconciliationService::toState)
					.collect(Collectors.toMap(MysqlArticleState::articleId, Function.identity()));

			tally.graphChecked += page.size();
			GraphReconciler.compareGraphPage(page, mysqlById).forEach(issue -> handle(issue, tally));

			afterId = page.get(page.size() - 1).mysqlArticleId();
			if (page.size() < properties.pageSize()) {
				return;
			}
		}
	}

	private void handle(ReconciliationIssue issue, Tally tally) {
		ReconciliationAction action = ReconciliationAction.REPORTED;
		if (properties.requeue() && issue.type().requeueable() && repair.requeue(issue)) {
			action = ReconciliationAction.REQUEUED;
			tally.requeued++;
		}
		tally.count(issue, action);
	}

	private static MysqlArticleState toState(ArticleNodeRef ref) {
		return new MysqlArticleState(ref.getArticleId(), ref.getAnalysisStatus(), ref.getNodeId());
	}

	/** 회차 동안 센 값. 건수는 모두 세고, 상세는 상한까지만 모은다. */
	private static final class Tally {

		private final int maxStored;
		private final List<RecordedIssue> stored = new ArrayList<>();
		private int mysqlChecked;
		private int graphChecked;
		private int missingGraph;
		private int nodeIdMismatch;
		private int unreflected;
		private int droppedWithGraph;
		private int orphanGraph;
		private int requeued;

		private Tally(int maxStored) {
			this.maxStored = maxStored;
		}

		private void count(ReconciliationIssue issue, ReconciliationAction action) {
			switch (issue.type()) {
				case MISSING_GRAPH -> missingGraph++;
				case NODE_ID_MISMATCH -> nodeIdMismatch++;
				case UNREFLECTED -> unreflected++;
				case DROPPED_WITH_GRAPH -> droppedWithGraph++;
				case ORPHAN_GRAPH -> orphanGraph++;
			}
			if (stored.size() < maxStored) {
				stored.add(new RecordedIssue(issue, action));
			}
		}

		private GraphReconciliationResult result() {
			return new GraphReconciliationResult(mysqlChecked, graphChecked, missingGraph, nodeIdMismatch,
					unreflected, droppedWithGraph, orphanGraph, requeued);
		}
	}
}

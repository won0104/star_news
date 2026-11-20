package com.starlightnews.backend.domain.article.reconcile;

import java.util.EnumMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import com.starlightnews.backend.global.alert.AlertNotifier;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.stereotype.Component;

/**
 * 대사 회차의 지표를 남기고, 어긋남을 찾거나 회차가 끊기면 알린다.
 *
 * <ul>
 *   <li>{@code graph.reconciliation.runs{status}}: COMPLETED · ABORTED 횟수</li>
 *   <li>{@code graph.reconciliation.issues{type}}: 마지막 회차에서 찾은 어긋남 수(유형별). 하루 한 번 전수로 세는
 *       값이라 누적이 아니라 마지막 값으로 둔다. 재시작 뒤 첫 회차 전까지는 0 이다</li>
 *   <li>{@code graph.reconciliation.requeued}: 마지막 회차에서 분석 대기로 되돌린 기사 수</li>
 * </ul>
 *
 * <p>어긋남은 기록 테이블에 남지만 아무도 열어 보지 않으면 그대로 굳는다. 되돌리기를 켜지 않은 기본 설정에서는
 * 사람이 판단해야 하므로 한 건이라도 있으면 유형별 건수를 알린다. 기사 ID 는 알림에 싣지 않고 기록 테이블에서 본다.
 */
@Component
public class GraphReconciliationMonitor {

	private final MeterRegistry registry;
	private final AlertNotifier notifier;
	private final Map<ReconciliationIssueType, AtomicInteger> lastIssues = new EnumMap<>(ReconciliationIssueType.class);
	private final AtomicInteger lastRequeued = new AtomicInteger();

	public GraphReconciliationMonitor(MeterRegistry registry, AlertNotifier notifier) {
		this.registry = registry;
		this.notifier = notifier;
		for (ReconciliationIssueType type : ReconciliationIssueType.values()) {
			AtomicInteger value = new AtomicInteger();
			lastIssues.put(type, value);
			Gauge.builder("graph.reconciliation.issues", value, AtomicInteger::get)
					.tag("type", type.name())
					.description("마지막 대사 회차에서 찾은 어긋남 수")
					.register(registry);
		}
		Gauge.builder("graph.reconciliation.requeued", lastRequeued, AtomicInteger::get)
				.description("마지막 대사 회차에서 분석 대기로 되돌린 기사 수")
				.register(registry);
	}

	void finished(GraphReconciliationResult result) {
		registry.counter("graph.reconciliation.runs", "status", GraphReconciliationRunStatus.COMPLETED.name())
				.increment();
		lastIssues.get(ReconciliationIssueType.MISSING_GRAPH).set(result.missingGraph());
		lastIssues.get(ReconciliationIssueType.NODE_ID_MISMATCH).set(result.nodeIdMismatch());
		lastIssues.get(ReconciliationIssueType.UNREFLECTED).set(result.unreflected());
		lastIssues.get(ReconciliationIssueType.DROPPED_WITH_GRAPH).set(result.droppedWithGraph());
		lastIssues.get(ReconciliationIssueType.ORPHAN_GRAPH).set(result.orphanGraph());
		lastRequeued.set(result.requeued());

		if (result.issues() > 0) {
			notifier.send(("MySQL·Neo4j 대사에서 어긋남 %d건을 찾았습니다. (그래프 누락 %d, 노드 ID 불일치 %d, 반영 누락 %d, "
					+ "제외 후 그래프 존재 %d, 고아 노드 %d, 분석 대기로 되돌림 %d) "
					+ "graph_reconciliation_issues 를 확인하세요.").formatted(
					result.issues(), result.missingGraph(), result.nodeIdMismatch(), result.unreflected(),
					result.droppedWithGraph(), result.orphanGraph(), result.requeued()));
		}
	}

	/** 회차가 예외로 끊겼다. 예외 메시지에는 쿼리·주소가 실릴 수 있어 종류만 알린다. */
	void aborted(RuntimeException failure) {
		registry.counter("graph.reconciliation.runs", "status", GraphReconciliationRunStatus.ABORTED.name())
				.increment();
		notifier.send("MySQL·Neo4j 대사 회차가 예외로 중단됐습니다. (%s) 서버 로그를 확인하세요."
				.formatted(failure.getClass().getSimpleName()));
	}
}

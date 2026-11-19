package com.starlightnews.backend.domain.article.reconcile;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

public interface GraphReconciliationIssueRepository extends JpaRepository<GraphReconciliationIssueRecord, Long> {

	List<GraphReconciliationIssueRecord> findByRunIdOrderByIssueIdAsc(Long runId);
}

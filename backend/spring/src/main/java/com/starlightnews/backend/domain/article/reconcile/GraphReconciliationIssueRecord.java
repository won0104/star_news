package com.starlightnews.backend.domain.article.reconcile;

import java.time.LocalDateTime;

import com.starlightnews.backend.global.enums.AnalysisStatus;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * 대사에서 찾은 어긋남 한 건의 기록. ({@code graph_reconciliation_issues})
 */
@Entity
@Table(name = "graph_reconciliation_issues")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class GraphReconciliationIssueRecord {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "issue_id")
	private Long issueId;

	@Column(name = "run_id", nullable = false)
	private Long runId;

	@Enumerated(EnumType.STRING)
	@Column(name = "issue_type", nullable = false, length = 32)
	private ReconciliationIssueType issueType;

	@Column(name = "article_id", nullable = false)
	private Long articleId;

	@Enumerated(EnumType.STRING)
	@Column(name = "mysql_status", length = 32)
	private AnalysisStatus mysqlStatus;

	// articles.node_id 와 같은 CHAR(36). 기본 VARCHAR 이면 validate 실패.
	@JdbcTypeCode(SqlTypes.CHAR)
	@Column(name = "mysql_node_id", length = 36)
	private String mysqlNodeId;

	@Column(name = "graph_node_id", length = 64)
	private String graphNodeId;

	@Enumerated(EnumType.STRING)
	@Column(name = "action", nullable = false, length = 32)
	private ReconciliationAction action;

	@Column(name = "created_at", nullable = false)
	private LocalDateTime createdAt;

	public GraphReconciliationIssueRecord(Long runId, ReconciliationIssue issue, ReconciliationAction action,
			LocalDateTime createdAt) {
		this.runId = runId;
		this.issueType = issue.type();
		this.articleId = issue.articleId();
		this.mysqlStatus = issue.mysqlStatus();
		this.mysqlNodeId = issue.mysqlNodeId();
		this.graphNodeId = issue.graphNodeId();
		this.action = action;
		this.createdAt = createdAt;
	}
}

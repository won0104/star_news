package com.starlightnews.backend.domain.trend.domain;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import com.starlightnews.backend.global.enums.NodeType;
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
 * 특정 집계 기준 시각의 트렌드 순위 항목. 집계 시점의 Node 제목과 기사 수를 함께 보존한다.
 */
@Entity
@Table(name = "trends")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Trend {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "trend_item_id")
	private Long trendItemId;

	@Column(name = "snapshot_at", nullable = false)
	private LocalDateTime snapshotAt;

	@Enumerated(EnumType.STRING)
	@Column(name = "node_type", nullable = false, length = 32)
	private NodeType nodeType;

	@JdbcTypeCode(SqlTypes.CHAR)
	@Column(name = "node_id", nullable = false, length = 36)
	private String nodeId;

	@Column(name = "node_title", nullable = false, length = 500)
	private String nodeTitle;

	@Column(nullable = false)
	private int rank;

	@Column(name = "article_count", nullable = false)
	private int articleCount;

	@Column(name = "trend_score", nullable = false, precision = 10, scale = 4)
	private BigDecimal trendScore;

	public Trend(
			LocalDateTime snapshotAt,
			NodeType nodeType,
			String nodeId,
			String nodeTitle,
			int rank,
			int articleCount,
			BigDecimal trendScore
	) {
		this.snapshotAt = snapshotAt;
		this.nodeType = nodeType;
		this.nodeId = nodeId;
		this.nodeTitle = nodeTitle;
		this.rank = rank;
		this.articleCount = articleCount;
		this.trendScore = trendScore;
	}
}

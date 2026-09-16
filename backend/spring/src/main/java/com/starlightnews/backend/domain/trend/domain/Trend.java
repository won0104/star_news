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
 * 특정 공개 회차의 트렌드 순위 항목. snapshotAt은 기사 집계 기준이 아닌 홈 공개 시각이다.
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

	@Column(name = "`rank`", nullable = false)
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

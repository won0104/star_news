package com.starlightnews.backend.domain.topic.domain;

import java.time.LocalDateTime;

import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.enums.TopicCode;
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
 * 특정 Topic과 공개 회차에 포함된 탐색 진입 Event 순위 항목.
 * 집계 결과를 보존하여 조회 요청이 Neo4j에 의존하지 않게 한다.
 */
@Entity
@Table(name = "topic_exploration_entries")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TopicExplorationEntry {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "topic_exploration_entry_id")
	private Long topicExplorationEntryId;

	@Column(name = "snapshot_at", nullable = false)
	private LocalDateTime snapshotAt;

	@Enumerated(EnumType.STRING)
	@Column(name = "topic_code", nullable = false, length = 32)
	private TopicCode topicCode;

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

	public TopicExplorationEntry(
			LocalDateTime snapshotAt,
			TopicCode topicCode,
			String nodeId,
			String nodeTitle,
			int rank,
			int articleCount
	) {
		this.snapshotAt = snapshotAt;
		this.topicCode = topicCode;
		this.nodeType = NodeType.EVENT;
		this.nodeId = nodeId;
		this.nodeTitle = nodeTitle;
		this.rank = rank;
		this.articleCount = articleCount;
	}
}

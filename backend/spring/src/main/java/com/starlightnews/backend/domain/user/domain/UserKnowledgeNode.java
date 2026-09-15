package com.starlightnews.backend.domain.user.domain;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 사용자별 지식 그래프 Node 참조·누적 정보. (user_knowledge_nodes)
 * 기사 열람으로 만들어진 Row 와 Node 직접 클릭으로 만들어진 Row 는 같은 PK 를 공유한다.
 * read_article_count(기사 신호)와 node_click_count(직접 탐색 신호)는 별개로 유지한다.
 */
@Entity
@Table(name = "user_knowledge_nodes")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserKnowledgeNode {

	@EmbeddedId
	private UserKnowledgeNodeId id;

	@Column(name = "node_label", nullable = false, length = 255)
	private String nodeLabel;

	@Column(name = "topic_code", length = 32)
	private String topicCode;

	@Column(name = "read_article_count", nullable = false)
	private int readArticleCount;

	@Column(name = "node_click_count", nullable = false)
	private int nodeClickCount;

	@Column(name = "first_seen_at", nullable = false)
	private LocalDateTime firstSeenAt;

	@Column(name = "last_seen_at", nullable = false)
	private LocalDateTime lastSeenAt;

	private UserKnowledgeNode(UserKnowledgeNodeId id, String nodeLabel, String topicCode,
			int readArticleCount, int nodeClickCount, LocalDateTime now) {
		this.id = id;
		this.nodeLabel = nodeLabel;
		this.topicCode = topicCode;
		this.readArticleCount = readArticleCount;
		this.nodeClickCount = nodeClickCount;
		this.firstSeenAt = now;
		this.lastSeenAt = now;
	}

	/** 개인 Node 가 아직 없을 때, 첫 클릭으로 새 Row 를 만든다. click_count=1, read_article_count=0. */
	public static UserKnowledgeNode forFirstClick(UserKnowledgeNodeId id, String nodeLabel, String topicCode,
			LocalDateTime now) {
		return new UserKnowledgeNode(id, nodeLabel, topicCode, 0, 1, now);
	}

	/**
	 * 개인 Node 가 아직 없을 때, 기사 열람으로 새 Row 를 만든다. read_article_count=1, click_count=0.
	 * 이 기사가 해당 Node 를 건드린 첫 고유 기사이므로 재열람이더라도 1 로 시작한다.
	 * (운영 경로는 UserKnowledgeNodeRepository#upsertRead 가 쓰고, 이 팩토리는 테스트 픽스처용이다)
	 */
	public static UserKnowledgeNode forFirstRead(UserKnowledgeNodeId id, String nodeLabel, String topicCode,
			LocalDateTime now) {
		return new UserKnowledgeNode(id, nodeLabel, topicCode, 1, 0, now);
	}

	/** 기존 Row 에 클릭 1회를 더한다. click_count +1, last_seen_at 갱신. 나머지 값은 유지. */
	public void registerClick(LocalDateTime now) {
		this.nodeClickCount += 1;
		this.lastSeenAt = now;
	}
}

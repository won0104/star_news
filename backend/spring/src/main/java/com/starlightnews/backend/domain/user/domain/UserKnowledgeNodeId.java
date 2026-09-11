package com.starlightnews.backend.domain.user.domain;

import java.io.Serializable;

import com.starlightnews.backend.global.enums.NodeType;
import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import lombok.AccessLevel;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * user_knowledge_nodes 테이블의 복합 기본키 (user_id, node_type, node_id).
 */
@Embeddable
@Getter
@EqualsAndHashCode
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserKnowledgeNodeId implements Serializable {

	@Column(name = "user_id")
	private Long userId;

	@Enumerated(EnumType.STRING)
	@Column(name = "node_type", length = 32)
	private NodeType nodeType;

	// user_knowledge_nodes.node_id 는 CHAR(36) 이므로 CHAR 로 매핑한다 (기본 VARCHAR 이면 validate 실패).
	@JdbcTypeCode(SqlTypes.CHAR)
	@Column(name = "node_id", length = 36)
	private String nodeId;

	public UserKnowledgeNodeId(Long userId, NodeType nodeType, String nodeId) {
		this.userId = userId;
		this.nodeType = nodeType;
		this.nodeId = nodeId;
	}
}

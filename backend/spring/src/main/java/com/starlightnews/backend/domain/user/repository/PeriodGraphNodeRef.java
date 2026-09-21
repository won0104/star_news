package com.starlightnews.backend.domain.user.repository;

import com.starlightnews.backend.global.enums.NodeType;

/** 기간 내 읽은 기사 하나와 그 기사에 직접 연결된 그래프 Node. */
public record PeriodGraphNodeRef(String articleNodeKey, NodeType nodeType, String nodeKey,
		String label, String topicCode) {
}

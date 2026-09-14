package com.starlightnews.backend.domain.user.dto;

import java.time.OffsetDateTime;

import com.starlightnews.backend.global.enums.NodeType;

/** 즐겨찾기 Node 목록의 한 항목. */
public record NodeBookmarkItem(
		NodeType nodeType,
		String nodeId,
		String name,
		OffsetDateTime bookmarkedAt
) {
}

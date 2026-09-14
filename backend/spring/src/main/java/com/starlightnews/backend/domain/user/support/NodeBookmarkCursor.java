package com.starlightnews.backend.domain.user.support;

import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.Base64;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;

/** 즐겨찾기 Node 목록의 정렬 마지막 값(bookmarkedAt, nodeType, nodeId)을 담는 커서. */
public record NodeBookmarkCursor(OffsetDateTime bookmarkedAt, NodeType nodeType, String nodeId) {

	private static final String DELIMITER = "|";

	/** URL-safe base64 문자열로 인코딩한다. */
	public String encode() {
		String raw = bookmarkedAt + DELIMITER + nodeType.name() + DELIMITER + nodeId;
		return Base64.getUrlEncoder().withoutPadding()
				.encodeToString(raw.getBytes(StandardCharsets.UTF_8));
	}

	/** 형식 또는 Node 유형이 올바르지 않은 커서는 INVALID_CURSOR로 거부한다. */
	public static NodeBookmarkCursor decode(String encoded) {
		try {
			String raw = new String(Base64.getUrlDecoder().decode(encoded), StandardCharsets.UTF_8);
			String[] parts = raw.split("\\|", -1);
			if (parts.length != 3 || parts[2].isBlank()) {
				throw invalidCursor();
			}

			OffsetDateTime bookmarkedAt = OffsetDateTime.parse(parts[0]);
			NodeType nodeType = NodeType.from(parts[1]).orElseThrow(NodeBookmarkCursor::invalidCursor);
			return new NodeBookmarkCursor(bookmarkedAt, nodeType, parts[2]);
		} catch (IllegalArgumentException | DateTimeParseException exception) {
			throw invalidCursor();
		}
	}

	private static BusinessException invalidCursor() {
		return new BusinessException(GraphErrorCode.INVALID_CURSOR);
	}
}

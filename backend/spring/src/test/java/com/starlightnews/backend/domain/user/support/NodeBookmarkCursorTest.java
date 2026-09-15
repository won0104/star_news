package com.starlightnews.backend.domain.user.support;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class NodeBookmarkCursorTest {

	@Test
	void 북마크시각_Node유형_NodeId를_불투명문자열로_왕복한다() {
		NodeBookmarkCursor cursor = new NodeBookmarkCursor(
				OffsetDateTime.of(2026, 9, 14, 9, 0, 0, 123_456_000, ZoneOffset.ofHours(9)),
				NodeType.ENTITY,
				"00000000-0000-0000-0000-000000000001");

		assertThat(NodeBookmarkCursor.decode(cursor.encode())).isEqualTo(cursor);
	}

	@Test
	void 잘못된형식은_INVALID_CURSOR이다() {
		assertThatThrownBy(() -> NodeBookmarkCursor.decode("not-a-cursor"))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(GraphErrorCode.INVALID_CURSOR));
	}
}

package com.starlightnews.backend.domain.user.dto;

import java.util.List;

import com.starlightnews.backend.global.enums.NodeType;

/** 그래프 Node 즐겨찾기 상태 부분 변경 결과. */
public record UpdateNodeBookmarksResponse(
		List<NodeBookmarkResult> results
) {

	public UpdateNodeBookmarksResponse {
		results = results == null ? List.of() : List.copyOf(results);
	}

	/** 요청한 Node의 최종 즐겨찾기 상태. */
	public record NodeBookmarkResult(
			NodeType nodeType,
			String nodeId,
			boolean bookmarked
	) {
	}
}

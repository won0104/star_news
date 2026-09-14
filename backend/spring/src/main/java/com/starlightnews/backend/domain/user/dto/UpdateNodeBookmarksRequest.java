package com.starlightnews.backend.domain.user.dto;

import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/** 그래프 Node 즐겨찾기 상태 부분 변경 요청. 요청에 포함되지 않은 Node는 변경하지 않는다. */
public record UpdateNodeBookmarksRequest(
		@NotNull List<@NotNull @Valid NodeBookmarkChange> changes
) {

	public UpdateNodeBookmarksRequest {
		if (changes != null) {
			changes = List.copyOf(changes);
		}
	}

	/** 한 Node의 목표 즐겨찾기 상태. */
	public record NodeBookmarkChange(
			@NotBlank String nodeType,
			@NotBlank String nodeId,
			@NotNull Boolean bookmarked
	) {
	}
}

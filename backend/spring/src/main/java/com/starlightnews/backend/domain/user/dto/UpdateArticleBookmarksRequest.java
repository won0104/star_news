package com.starlightnews.backend.domain.user.dto;

import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

/** 기사 북마크 상태 부분 변경 요청. 요청에 포함되지 않은 기사는 변경하지 않는다. */
public record UpdateArticleBookmarksRequest(
		@NotNull List<@NotNull @Valid ArticleBookmarkChange> changes
) {

	public UpdateArticleBookmarksRequest {
		if (changes != null) {
			changes = List.copyOf(changes);
		}
	}

	/** 한 기사의 목표 북마크 상태. */
	public record ArticleBookmarkChange(
			@NotNull @Positive Long articleId,
			@NotNull Boolean bookmarked
	) {
	}
}

package com.starlightnews.backend.domain.user.dto;

import java.util.List;

/** 기사 북마크 상태 부분 변경 결과. */
public record UpdateArticleBookmarksResponse(
		List<ArticleBookmarkResult> results
) {

	public UpdateArticleBookmarksResponse {
		results = results == null ? List.of() : List.copyOf(results);
	}

	/** 요청한 기사의 최종 북마크 상태. */
	public record ArticleBookmarkResult(
			long articleId,
			boolean bookmarked
	) {
	}
}

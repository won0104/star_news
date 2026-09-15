package com.starlightnews.backend.domain.article.dto;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

/**
 * GNews top-headlines 응답. (<a href="https://docs.gnews.io">GNews API v4</a>)
 * 우리가 쓰지 않는 필드(id, image, lang 등)는 매핑하지 않고 무시한다.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record GNewsArticlesResponse(int totalArticles, List<GNewsArticle> articles) {

	public GNewsArticlesResponse {
		articles = articles == null ? List.of() : articles.stream()
				.filter(java.util.Objects::nonNull).toList();
	}

	/** 기사 한 건. content 는 요금제·기사에 따라 null 이거나 잘려 올 수 있다. */
	@JsonIgnoreProperties(ignoreUnknown = true)
	public record GNewsArticle(
			String title,
			String description,
			String content,
			String url,
			String publishedAt,
			Source source) {
	}

	/** 기사를 제공한 언론사. */
	@JsonIgnoreProperties(ignoreUnknown = true)
	public record Source(String name, String url) {
	}
}

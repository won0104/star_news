package com.starlightnews.backend.domain.user.domain;

import java.io.Serializable;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import lombok.AccessLevel;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * user_article_favorites 테이블의 복합 기본키 (user_id, article_id).
 */
@Embeddable
@Getter
@EqualsAndHashCode
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserArticleFavoriteId implements Serializable {

	@Column(name = "user_id")
	private Long userId;

	@Column(name = "article_id")
	private Long articleId;

	public UserArticleFavoriteId(Long userId, Long articleId) {
		this.userId = userId;
		this.articleId = articleId;
	}
}

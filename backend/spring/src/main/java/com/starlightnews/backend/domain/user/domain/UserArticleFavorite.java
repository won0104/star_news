package com.starlightnews.backend.domain.user.domain;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * 사용자의 기사 즐겨찾기(북마크). (user_article_favorites)
 * 추가·삭제는 별도 API 담당이며, 여기서는 조회에 사용한다.
 */
@Entity
@Table(name = "user_article_favorites")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserArticleFavorite {

	@EmbeddedId
	private UserArticleFavoriteId id;

	@Column(name = "favorited_at", nullable = false)
	private LocalDateTime favoritedAt;

	public UserArticleFavorite(UserArticleFavoriteId id, LocalDateTime favoritedAt) {
		this.id = id;
		this.favoritedAt = favoritedAt;
	}
}

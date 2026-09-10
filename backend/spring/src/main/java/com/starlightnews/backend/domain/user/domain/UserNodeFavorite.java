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
 * 사용자의 지식 그래프 Node 즐겨찾기. (user_node_favorites)
 */
@Entity
@Table(name = "user_node_favorites")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserNodeFavorite {

	@EmbeddedId
	private UserNodeFavoriteId id;

	@Column(name = "favorited_at", nullable = false)
	private LocalDateTime favoritedAt;

	public UserNodeFavorite(UserNodeFavoriteId id, LocalDateTime favoritedAt) {
		this.id = id;
		this.favoritedAt = favoritedAt;
	}
}

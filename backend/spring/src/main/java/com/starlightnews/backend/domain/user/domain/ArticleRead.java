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
 * 뉴스 카드 클릭 기준 기사 열람 기록. (article_reads)
 * 개인 그래프 조회에서 Topic 별 읽은 기사 수 집계·읽은 기사 판별에 사용하는 읽기 전용 엔티티.
 */
@Entity
@Table(name = "article_reads")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ArticleRead {

	@EmbeddedId
	private ArticleReadId id;

	@Column(name = "first_read_at", nullable = false)
	private LocalDateTime firstReadAt;

	@Column(name = "last_read_at", nullable = false)
	private LocalDateTime lastReadAt;

	@Column(name = "click_count", nullable = false)
	private int clickCount;

	public ArticleRead(ArticleReadId id, LocalDateTime firstReadAt, LocalDateTime lastReadAt, int clickCount) {
		this.id = id;
		this.firstReadAt = firstReadAt;
		this.lastReadAt = lastReadAt;
		this.clickCount = clickCount;
	}
}

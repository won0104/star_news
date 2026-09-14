package com.starlightnews.backend.domain.article.domain;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * 기사. (articles)
 * 관련 기사 목록에 필요한 필드만 매핑한 읽기용 부분 엔티티. 전문·요약·원문 URL 등은 기사 상세 API 담당.
 */
@Entity
@Table(name = "articles")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Article {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "article_id")
	private Long articleId;

	@Column(nullable = false, length = 500)
	private String title;

	@Column(name = "published_at", nullable = false)
	private LocalDateTime publishedAt;

	@Column(name = "topic_code", length = 32)
	private String topicCode;

	@JdbcTypeCode(SqlTypes.LONGVARCHAR)
	@Column(name = "summary")
	private String summary;

	/** Neo4j Article Node 의 nodeId. AI 분석 전이면 null 이라 Neo4j 에 대응 Node 가 없다. */
	// articles.node_id 는 CHAR(36) 이므로 CHAR 로 매핑한다 (기본 VARCHAR 이면 validate 실패).
	@JdbcTypeCode(SqlTypes.CHAR)
	@Column(name = "node_id", length = 36)
	private String nodeId;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "organization_id")
	private NewsOrganization organization;

	public Article(String title, LocalDateTime publishedAt, NewsOrganization organization) {
		this.title = title;
		this.publishedAt = publishedAt;
		this.organization = organization;
	}
}

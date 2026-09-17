package com.starlightnews.backend.domain.article.domain;

import java.time.LocalDateTime;

import com.starlightnews.backend.domain.article.support.ArticleUrls;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.ContentType;
import com.starlightnews.backend.global.enums.SummaryStatus;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * 기사. (articles)
 *
 * <p>수집한 기사를 저장하면서 쓰기에 필요한 필드까지 매핑했다. 제목·본문·원문 URL 은 수집 단계가 채우고,
 * 분류(topic_code·subtopic_code)와 요약은 이후 분석·요약 단계가 채운다.
 */
@Entity
@Table(name = "articles", uniqueConstraints =
		// 실제 스키마(V1 마이그레이션)의 제약을 엔티티에도 선언한다. 같은 기사를 다시 수집했을 때
		// 중복 저장을 막는 키이고, H2 테스트 DB 는 엔티티에서 스키마를 만들어 여기 없으면 검증이 안 된다.
		@UniqueConstraint(name = "uk_articles_url_hash", columnNames = "url_hash"))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Article {

	/** 픽스처 생성자가 만드는 url 의 앞부분. 제목이 다르면 url_hash 도 달라진다. */
	private static final String FIXTURE_URL_PREFIX = "https://article.fixture.test/";

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	@Column(name = "article_id")
	private Long articleId;

	@Column(nullable = false, length = 500)
	private String title;

	/** 언론사 원문 주소. */
	@JdbcTypeCode(SqlTypes.LONGVARCHAR)
	@Column(nullable = false)
	private String url;

	/** 정규화한 url 의 SHA-256. 같은 기사를 다시 수집했는지 판별하는 키다. */
	// articles.url_hash 는 BINARY(32) 이므로 BINARY 로 매핑한다 (기본 VARBINARY 이면 validate 실패).
	@JdbcTypeCode(SqlTypes.BINARY)
	@Column(name = "url_hash", nullable = false, length = 32)
	private byte[] urlHash;

	@Column(name = "published_at", nullable = false)
	private LocalDateTime publishedAt;

	/** 제공처가 준 원본 분류. 우리 TopicCode 로 변환하지 않고 그대로 보존한다. */
	@Column(name = "source_category", length = 100)
	private String sourceCategory;

	/** 분석 단계가 채우는 서비스 대표 분야. 수집 시점에는 비어 있다. */
	@Column(name = "topic_code", length = 32)
	private String topicCode;

	@JdbcTypeCode(SqlTypes.LONGVARCHAR)
	@Column(nullable = false)
	private String content;

	@Enumerated(EnumType.STRING)
	@Column(name = "content_type", nullable = false, length = 32)
	private ContentType contentType;

	@JdbcTypeCode(SqlTypes.LONGVARCHAR)
	@Column(name = "summary")
	private String summary;

	@Enumerated(EnumType.STRING)
	@Column(name = "summary_status", nullable = false, length = 32)
	private SummaryStatus summaryStatus;

	@Column(name = "summary_generated_at")
	private LocalDateTime summaryGeneratedAt;

	/** Neo4j Article Node 의 nodeId. AI 분석 전이면 null 이라 Neo4j 에 대응 Node 가 없다. */
	// articles.node_id 는 CHAR(36) 이므로 CHAR 로 매핑한다 (기본 VARCHAR 이면 validate 실패).
	@JdbcTypeCode(SqlTypes.CHAR)
	@Column(name = "node_id", length = 36)
	private String nodeId;

	@Enumerated(EnumType.STRING)
	@Column(name = "analysis_status", nullable = false, length = 32)
	private AnalysisStatus analysisStatus;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "organization_id")
	private NewsOrganization organization;

	/**
	 * 테스트 픽스처용 생성자. 저장 경로는 {@code ArticleRepository#insertIfAbsent} 네이티브 Upsert 라
	 * 운영 코드는 이 생성자를 쓰지 않는다. NOT NULL 인 url·본문 계열은 제목에서 만들어 채운다.
	 */
	public Article(String title, LocalDateTime publishedAt, NewsOrganization organization) {
		this(title, publishedAt, organization, null, AnalysisStatus.PROCESSING);
	}

	/** 테스트 픽스처용 생성자. */
	public Article(String title, LocalDateTime publishedAt, NewsOrganization organization,
			String summary, AnalysisStatus analysisStatus) {
		this.title = title;
		this.publishedAt = publishedAt;
		this.organization = organization;
		this.summary = summary;
		this.summaryStatus = summary == null ? SummaryStatus.NOT_REQUESTED : SummaryStatus.COMPLETED;
		this.analysisStatus = analysisStatus;
		this.url = FIXTURE_URL_PREFIX + title;
		this.urlHash = ArticleUrls.hash(this.url);
		this.content = title;
		this.contentType = ContentType.FULL_TEXT;
	}
}

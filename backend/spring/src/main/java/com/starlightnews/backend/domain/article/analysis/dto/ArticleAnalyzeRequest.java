package com.starlightnews.backend.domain.article.analysis.dto;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;

/**
 * FastAPI {@code POST /internal/v1/articles/analyze} 요청 본문.
 *
 * <p>필드 이름은 FastAPI {@code ArticleAnalyzeRequest}(CamelModel)와 맞춘다.
 *
 * @param articleId  MySQL articles.article_id. Neo4j Article 의 mysqlArticleId 가 된다
 * @param sourceId   MySQL news_organizations.organization_id. 언론사 Entity 를 찾는 키다
 * @param publishedAt 반드시 오프셋을 붙인다. 없으면 FastAPI 가 naive datetime 으로 받아 Neo4j 에
 *                   LocalDateTime 으로 저장하는데, Spring 그래프 조회는 이 값을 ZonedDateTime 으로
 *                   읽으므로 분석된 기사가 관련 기사 조회에서 깨진다
 */
public record ArticleAnalyzeRequest(
		long articleId,
		String title,
		String content,
		long sourceId,
		String sourceName,
		OffsetDateTime publishedAt
) {

	/** DB DATETIME(6) 은 KST 벽시계로 저장된다. */
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	public static ArticleAnalyzeRequest of(long articleId, String title, String content,
			long sourceId, String sourceName, LocalDateTime publishedAt) {
		return new ArticleAnalyzeRequest(articleId, title, content, sourceId, sourceName,
				publishedAt.atOffset(KST));
	}
}

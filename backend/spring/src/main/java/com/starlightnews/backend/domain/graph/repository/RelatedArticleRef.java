package com.starlightnews.backend.domain.graph.repository;

import java.time.OffsetDateTime;

/**
 * Neo4j 에서 조회한, Node 와 연결된 Article 의 정렬·커서용 키.
 * 화면용 정보(제목·언론사)는 MySQL 에서 별도로 조회한다.
 */
public record RelatedArticleRef(
		long articleId,
		OffsetDateTime publishedAt
) {
}

package com.starlightnews.backend.domain.article.dto;

import java.time.LocalDateTime;

import com.starlightnews.backend.global.enums.ContentType;

/**
 * 외부에서 수집해 검증·정규화를 마친 기사 한 건. 저장 직전 형태다.
 *
 * <p>topicCode·subtopicCode 는 담지 않는다. 기사 분류는 FastAPI 분석 단계가 담당하고,
 * 수집 단계는 제공처가 준 원본 분류를 sourceCategory 에 그대로 남긴다.
 *
 * @param urlHash        정규화한 url 의 SHA-256(32바이트). articles.url_hash 의 중복 판별 키다.
 * @param publishedAt    KST 벽시계 기준 발행 시각. (DB DATETIME(6) 이 KST 로 저장된다)
 * @param sourceCategory 제공처의 원본 분류. 우리 TopicCode 로 변환하지 않는다.
 */
public record CollectedArticle(
		String title,
		String url,
		byte[] urlHash,
		LocalDateTime publishedAt,
		String content,
		ContentType contentType,
		String sourceCategory,
		String organizationName,
		String organizationDomain) {
}

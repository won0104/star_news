package com.starlightnews.backend.domain.recommendation.dto;

import java.time.OffsetDateTime;
import java.util.List;

import com.starlightnews.backend.global.enums.TopicCode;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 추천 Event 상세 조회 응답.
 *
 * <p>요약은 추천 배치가 회차를 저장한 직후에 만든다. 이 API 는 만들지 않고 읽기만 한다.
 */
public record RecommendationDetailResponse(

		@Schema(description = "추천 상세 조회 키", example = "10241")
		long userRecommendationId,

		@Schema(description = "Neo4j Event 의 nodeId", example = "00000020-0920-4000-8000-000000000001")
		String eventId,

		@Schema(description = "Event 표시 이름", example = "한국은행 1월 기준금리 동결")
		String label,

		@Schema(description = "Event 의 Topic", example = "ECONOMY")
		TopicCode topicCode,

		@Schema(description = """
				Event 요약. 아직 만들어지지 않았거나 생성에 실패했으면 null 이다.
				공개 시각까지 생성이 끝나지 않는 경우가 있어 화면은 null 을 정상 상태로 다뤄야 한다.""",
				nullable = true)
		String contextSummary,

		@Schema(description = "Event 를 다루는 기사 목록. 관련도 높은 순")
		List<Article> articles
) {

	public record Article(

			@Schema(description = "MySQL Article PK", example = "930001")
			long articleId,

			@Schema(description = "기사 제목", example = "한국은행 1월 기준금리 동결")
			String title,

			@Schema(description = "발행 언론사명", example = "연합뉴스")
			String organizationName,

			@Schema(description = "언론사가 기사를 발행한 시각", example = "2024-01-11T09:52:15+09:00")
			OffsetDateTime publishedAt,

			@Schema(description = "기사 Topic. AI 분석 전이면 null", nullable = true, example = "ECONOMY")
			String topicCode,

			@Schema(description = "언론사 원문 URL", example = "https://www.yna.co.kr/view/AKR20240111")
			String originalUrl
	) {
	}
}

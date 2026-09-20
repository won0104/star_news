package com.starlightnews.backend.domain.user.dto;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 최근 3개월 기사 열람과 개인 지식 Node 탐색 기록으로 구성한 사용자 뉴스 리포트.
 */
public record NewsReportResponse(

		@Schema(description = "리포트 집계 기간")
		Period period,

		@Schema(description = "최근 3개월 동안 읽은 고유 기사 수", example = "67")
		long totalReadArticleCount,

		@Schema(description = "언론사별 읽은 기사 수와 전체 대비 비율")
		List<SourceRead> sourceReads,

		@Schema(description = "최근 12개 주차의 분야별 최초 열람 기사 수. 데이터가 있는 주차만 포함")
		List<WeeklyTopicTrend> weeklyTopicTrend,

		@Schema(description = "최근 3개월 동안 접한 ENTITY 중 누적 읽기 상위 Node")
		List<TopicLandscapeNode> topicLandscape,

		@Schema(description = "리포트 생성 시각", example = "2026-09-02T21:00:00+09:00")
		OffsetDateTime generatedAt
) {

	@Schema(name = "NewsReportPeriod")
	public record Period(
			@Schema(description = "조회 시작일(KST, 포함)", example = "2026-06-02")
			LocalDate from,

			@Schema(description = "조회 종료일(KST, 포함)", example = "2026-09-02")
			LocalDate to
	) {
	}

	@Schema(name = "NewsReportSourceRead")
	public record SourceRead(
			@Schema(description = "언론사 ID", example = "1")
			long organizationId,

			@Schema(description = "언론사명", example = "연합뉴스")
			String organizationName,

			@Schema(description = "해당 언론사의 고유 기사 수", example = "18")
			long readArticleCount,

			@Schema(description = "전체 읽은 기사 수 대비 비율(%)", example = "26.9")
			double ratio
	) {
	}

	@Schema(name = "NewsReportWeeklyTopicTrend")
	public record WeeklyTopicTrend(
			@Schema(description = "주차 시작일(월요일)", example = "2026-08-17")
			LocalDate weekStart,

			@Schema(description = "해당 주차의 분야별 최초 열람 기사 수")
			List<WeeklyTopic> topics
	) {
	}

	@Schema(name = "NewsReportWeeklyTopic")
	public record WeeklyTopic(
			@Schema(description = "기사 Topic 코드", example = "ECONOMY")
			String topicCode,

			@Schema(description = "Topic 한글 표시명", example = "경제")
			String topicName,

			@Schema(description = "해당 주차에 처음 읽은 고유 기사 수", example = "5")
			long readArticleCount
	) {
	}

	@Schema(name = "NewsReportTopicLandscapeNode")
	public record TopicLandscapeNode(
			@Schema(description = "Node 유형. 뉴스 리포트 주제 지형은 ENTITY만 반환", example = "ENTITY")
			String nodeType,

			@Schema(description = "Node 업무 ID(nodeId)", example = "00000024-0920-4000-8000-000000000001")
			String nodeKey,

			@Schema(description = "Node 화면 표시명", example = "HBM")
			String label,

			@Schema(description = "Node 대표 Topic 코드. 분류되지 않았으면 null",
					example = "IT_SCIENCE", nullable = true)
			String topicCode,

			@Schema(description = "로그인 사용자가 전 기간 동안 이 Entity와 연결된 고유 기사를 읽은 수", example = "2")
			long userReadArticleCount,

			@Schema(description = "모든 사용자가 전 기간 동안 이 Entity와 연결된 고유 기사를 읽은 수의 합계", example = "126")
			long globalReadArticleCount,

			@Schema(description = "가로축 표시 위치(%). 개인 누적 읽기 수를 현재 응답 내에서 12~88로 정규화",
					example = "63.2")
			double x,

			@Schema(description = "세로축 표시 위치(%). 전체 사용자 누적 읽기 수가 클수록 위에 오도록 12~88로 정규화",
					example = "22.0")
			double y,

			@Schema(description = "개인 누적 읽기 정규화 점수가 중간 이상인 Entity 강조 여부", example = "true")
			boolean strong,

			@Schema(description = "Node를 처음 접한 시각", example = "2026-08-28T14:10:00+09:00")
			OffsetDateTime firstSeenAt,

			@Schema(description = "Node를 마지막으로 접한 시각", example = "2026-08-31T11:20:00+09:00")
			OffsetDateTime lastSeenAt,

			@Schema(description = "조회 기간 안에 처음 접했으면 NEW, 이전부터 알던 Node면 FAMILIAR",
					example = "NEW")
			Familiarity familiarity
	) {
	}

	public enum Familiarity {
		NEW,
		FAMILIAR
	}
}

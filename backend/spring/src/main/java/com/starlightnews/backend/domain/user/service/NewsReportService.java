package com.starlightnews.backend.domain.user.service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Clock;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.temporal.TemporalAdjusters;
import java.util.Arrays;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import com.starlightnews.backend.domain.user.dto.NewsReportResponse;
import com.starlightnews.backend.domain.user.dto.NewsReportResponse.Familiarity;
import com.starlightnews.backend.domain.user.dto.NewsReportResponse.SourceRead;
import com.starlightnews.backend.domain.user.dto.NewsReportResponse.TopicLandscapeNode;
import com.starlightnews.backend.domain.user.dto.NewsReportResponse.WeeklyTopic;
import com.starlightnews.backend.domain.user.dto.NewsReportResponse.WeeklyTopicTrend;
import com.starlightnews.backend.domain.user.exception.NewsReportErrorCode;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository.FirstReadTopicRow;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository.NewsReportEntityLandscapeRow;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * MySQL의 기사 열람과 사용자 지식 Node Snapshot을 최근 3개월 뉴스 리포트로 조합한다.
 * 캐시와 Neo4j는 사용하지 않는다.
 */
@Slf4j
@Service
public class NewsReportService {

	private static final int PERIOD_MONTHS = 3;
	private static final int WEEK_COUNT = 12;
	private static final int TOPIC_LANDSCAPE_LIMIT = 12;
	private static final double LANDSCAPE_MIN_POSITION = 12.0;
	private static final double LANDSCAPE_POSITION_RANGE = 76.0;
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	private final ArticleReadRepository articleReadRepository;
	private final UserKnowledgeNodeRepository userKnowledgeNodeRepository;
	private final Clock newsReportClock;

	public NewsReportService(ArticleReadRepository articleReadRepository,
			UserKnowledgeNodeRepository userKnowledgeNodeRepository,
			@Qualifier("newsReportClock") Clock newsReportClock) {
		this.articleReadRepository = articleReadRepository;
		this.userKnowledgeNodeRepository = userKnowledgeNodeRepository;
		this.newsReportClock = newsReportClock;
	}

	@Transactional(readOnly = true)
	public NewsReportResponse getNewsReport(Long userId) {
		try {
			OffsetDateTime generatedAt = OffsetDateTime.now(newsReportClock);
			LocalDate to = generatedAt.toLocalDate();
			LocalDate from = to.minusMonths(PERIOD_MONTHS);
			LocalDateTime fromInclusive = from.atStartOfDay();
			LocalDateTime toExclusive = to.plusDays(1).atStartOfDay();

			long totalReadArticleCount = articleReadRepository.countRecentReadArticles(
					userId, fromInclusive, toExclusive);
			List<SourceRead> sourceReads = articleReadRepository.countRecentReadArticlesBySource(
					userId, fromInclusive, toExclusive).stream()
					.map(row -> new SourceRead(
							row.getOrganizationId(),
							row.getOrganizationName(),
							row.getCount(),
							calculateRatio(row.getCount(), totalReadArticleCount)))
					.toList();

			LocalDate currentWeekStart = to.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY));
			LocalDate weeklyFrom = currentWeekStart.minusWeeks(WEEK_COUNT - 1L);

			List<WeeklyTopicTrend> weeklyTopicTrend = buildWeeklyTopicTrend(
					articleReadRepository.findFirstReadTopics(userId, weeklyFrom.atStartOfDay(), toExclusive),
					weeklyFrom);
			List<TopicLandscapeNode> topicLandscape = buildTopicLandscape(
					userKnowledgeNodeRepository.findEntityLandscapeForNewsReport(
							userId, fromInclusive, toExclusive, TOPIC_LANDSCAPE_LIMIT),
					fromInclusive);

			return new NewsReportResponse(
					new NewsReportResponse.Period(from, to),
					totalReadArticleCount,
					sourceReads,
					weeklyTopicTrend,
					topicLandscape,
					generatedAt);
		} catch (RuntimeException exception) {
			log.error("뉴스 리포트 조회 또는 응답 조합에 실패했습니다. userId={}", userId, exception);
			throw new BusinessException(NewsReportErrorCode.NEWS_REPORT_AGGREGATION_FAILED);
		}
	}

	private double calculateRatio(long count, long totalCount) {
		if (totalCount == 0) {
			return 0.0;
		}
		return BigDecimal.valueOf(count)
				.multiply(BigDecimal.valueOf(100))
				.divide(BigDecimal.valueOf(totalCount), 1, RoundingMode.HALF_UP)
				.doubleValue();
	}

	private List<WeeklyTopicTrend> buildWeeklyTopicTrend(List<FirstReadTopicRow> rows,
			LocalDate weeklyFrom) {
		Map<LocalDate, EnumMap<TopicCode, Long>> countsByWeek = new TreeMap<>();
		for (int weekIndex = 0; weekIndex < WEEK_COUNT; weekIndex++) {
			countsByWeek.put(weeklyFrom.plusWeeks(weekIndex), new EnumMap<>(TopicCode.class));
		}

		for (FirstReadTopicRow row : rows) {
			TopicCode.from(row.getTopicCode()).ifPresent(topicCode -> {
				LocalDate weekStart = row.getFirstReadAt().toLocalDate()
						.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY));
				EnumMap<TopicCode, Long> weeklyCounts = countsByWeek.get(weekStart);
				if (weeklyCounts != null) {
					weeklyCounts.merge(topicCode, 1L, Long::sum);
				}
			});
		}

		return countsByWeek.entrySet().stream()
				.map(entry -> new WeeklyTopicTrend(entry.getKey(), toWeeklyTopics(entry.getValue())))
				.toList();
	}

	private List<WeeklyTopic> toWeeklyTopics(EnumMap<TopicCode, Long> counts) {
		return Arrays.stream(TopicCode.values())
				.map(topicCode -> new WeeklyTopic(
						topicCode.name(), topicCode.labelKo(), counts.getOrDefault(topicCode, 0L)))
				.toList();
	}

	private List<TopicLandscapeNode> buildTopicLandscape(List<NewsReportEntityLandscapeRow> rows,
			LocalDateTime fromInclusive) {
		if (rows.isEmpty()) {
			return List.of();
		}

		double minUserLog = rows.stream()
				.mapToDouble(row -> Math.log1p(row.getUserReadArticleCount()))
				.min()
				.orElseThrow();
		double maxUserLog = rows.stream()
				.mapToDouble(row -> Math.log1p(row.getUserReadArticleCount()))
				.max()
				.orElseThrow();
		double minGlobalLog = rows.stream()
				.mapToDouble(row -> Math.log1p(row.getGlobalReadArticleCount()))
				.min()
				.orElseThrow();
		double maxGlobalLog = rows.stream()
				.mapToDouble(row -> Math.log1p(row.getGlobalReadArticleCount()))
				.max()
				.orElseThrow();
		boolean hasUserCountRange = maxUserLog > minUserLog;

		return rows.stream()
				.map(node -> toLandscapeNode(node, fromInclusive,
						minUserLog, maxUserLog, minGlobalLog, maxGlobalLog, hasUserCountRange))
				.toList();
	}

	private TopicLandscapeNode toLandscapeNode(NewsReportEntityLandscapeRow node,
			LocalDateTime fromInclusive, double minUserLog, double maxUserLog,
			double minGlobalLog, double maxGlobalLog, boolean hasUserCountRange) {
		Familiarity familiarity = node.getFirstSeenAt().isBefore(fromInclusive)
				? Familiarity.FAMILIAR : Familiarity.NEW;
		double userScore = normalizeLogCount(
				node.getUserReadArticleCount(), minUserLog, maxUserLog);
		double globalScore = normalizeLogCount(
				node.getGlobalReadArticleCount(), minGlobalLog, maxGlobalLog);
		return new TopicLandscapeNode(
				node.getNodeType(),
				node.getNodeKey(),
				node.getNodeLabel(),
				node.getTopicCode(),
				node.getUserReadArticleCount(),
				node.getGlobalReadArticleCount(),
				toPosition(userScore),
				toPosition(1.0 - globalScore),
				hasUserCountRange && userScore >= 0.5,
				node.getFirstSeenAt().atOffset(KST),
				node.getLastSeenAt().atOffset(KST),
				familiarity);
	}

	private double normalizeLogCount(long count, double minLog, double maxLog) {
		if (maxLog == minLog) {
			return 0.5;
		}
		return (Math.log1p(count) - minLog) / (maxLog - minLog);
	}

	private double toPosition(double score) {
		return BigDecimal.valueOf(LANDSCAPE_MIN_POSITION + score * LANDSCAPE_POSITION_RANGE)
				.setScale(1, RoundingMode.HALF_UP)
				.doubleValue();
	}
}

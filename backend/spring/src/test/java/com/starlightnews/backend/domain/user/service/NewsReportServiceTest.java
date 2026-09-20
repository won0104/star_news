package com.starlightnews.backend.domain.user.service;

import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.user.dto.NewsReportResponse;
import com.starlightnews.backend.domain.user.dto.NewsReportResponse.Familiarity;
import com.starlightnews.backend.domain.user.exception.NewsReportErrorCode;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository.FirstReadTopicRow;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository.SourceReadCount;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository.NewsReportEntityLandscapeRow;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.assertj.core.groups.Tuple.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class NewsReportServiceTest {

	private static final ZoneId KST = ZoneId.of("Asia/Seoul");
	private static final Clock FIXED_CLOCK = Clock.fixed(
			Instant.parse("2026-09-02T12:00:00Z"), KST);

	@Mock
	private ArticleReadRepository articleReadRepository;

	@Mock
	private UserKnowledgeNodeRepository userKnowledgeNodeRepository;

	private NewsReportService newsReportService;

	@BeforeEach
	void setUp() {
		newsReportService = new NewsReportService(
				articleReadRepository, userKnowledgeNodeRepository, FIXED_CLOCK);
	}

	@Test
	void 최근_3개월_리포트를_집계한다() {
		LocalDateTime from = LocalDateTime.of(2026, 6, 2, 0, 0);
		LocalDateTime toExclusive = LocalDateTime.of(2026, 9, 3, 0, 0);
		LocalDateTime weeklyFrom = LocalDateTime.of(2026, 6, 15, 0, 0);

		given(articleReadRepository.countRecentReadArticles(1L, from, toExclusive)).willReturn(67L);
		given(articleReadRepository.countRecentReadArticlesBySource(1L, from, toExclusive))
				.willReturn(List.of(source(1L, "연합뉴스", 18L), source(2L, "테크뉴스", 3L)));
		given(articleReadRepository.findFirstReadTopics(1L, weeklyFrom, toExclusive))
				.willReturn(List.of(
						weeklyRow(LocalDateTime.of(2026, 8, 17, 9, 0), "ECONOMY"),
						weeklyRow(LocalDateTime.of(2026, 8, 18, 9, 0), "ECONOMY"),
						weeklyRow(LocalDateTime.of(2026, 8, 19, 9, 0), "IT_SCIENCE"),
						weeklyRow(LocalDateTime.of(2026, 8, 24, 9, 0), "UNKNOWN")));

		NewsReportEntityLandscapeRow familiar = landscapeRow(
				"00000020-0920-4000-8000-000000000001", "한국은행", "ECONOMY",
				LocalDateTime.of(2026, 5, 20, 10, 30), LocalDateTime.of(2026, 8, 31, 9, 10), 8, 126);
		NewsReportEntityLandscapeRow fresh = landscapeRow(
				"00000024-0920-4000-8000-000000000001", "HBM", null,
				LocalDateTime.of(2026, 8, 28, 14, 10), LocalDateTime.of(2026, 8, 31, 11, 20), 2, 40);
		given(userKnowledgeNodeRepository.findEntityLandscapeForNewsReport(
				1L, from, toExclusive, 12))
				.willReturn(List.of(fresh, familiar));

		NewsReportResponse response = newsReportService.getNewsReport(1L);

		assertThat(response.period().from()).isEqualTo(LocalDate.of(2026, 6, 2));
		assertThat(response.period().to()).isEqualTo(LocalDate.of(2026, 9, 2));
		assertThat(response.totalReadArticleCount()).isEqualTo(67L);
		assertThat(response.sourceReads())
				.extracting(NewsReportResponse.SourceRead::organizationName,
						NewsReportResponse.SourceRead::readArticleCount,
						NewsReportResponse.SourceRead::ratio)
				.containsExactly(tuple("연합뉴스", 18L, 26.9), tuple("테크뉴스", 3L, 4.5));
		assertThat(response.weeklyTopicTrend()).hasSize(12);
		assertThat(response.weeklyTopicTrend().getFirst().weekStart())
				.isEqualTo(LocalDate.of(2026, 6, 15));
		assertThat(response.weeklyTopicTrend().getLast().weekStart())
				.isEqualTo(LocalDate.of(2026, 8, 31));
		NewsReportResponse.WeeklyTopicTrend weekOfAugust17 = response.weeklyTopicTrend().stream()
				.filter(week -> week.weekStart().equals(LocalDate.of(2026, 8, 17)))
				.findFirst()
				.orElseThrow();
		assertThat(weekOfAugust17.topics())
				.extracting(NewsReportResponse.WeeklyTopic::topicCode,
						NewsReportResponse.WeeklyTopic::topicName,
						NewsReportResponse.WeeklyTopic::readArticleCount)
				.containsExactly(
						tuple("POLITICS", "정치", 0L),
						tuple("ECONOMY", "경제", 2L),
						tuple("SOCIETY", "사회", 0L),
						tuple("CULTURE", "문화", 0L),
						tuple("INTERNATIONAL", "국제", 0L),
						tuple("SPORTS", "스포츠", 0L),
						tuple("IT_SCIENCE", "IT·과학", 1L));
		assertThat(response.topicLandscape())
				.extracting(NewsReportResponse.TopicLandscapeNode::nodeType,
						NewsReportResponse.TopicLandscapeNode::topicCode,
						NewsReportResponse.TopicLandscapeNode::userReadArticleCount,
						NewsReportResponse.TopicLandscapeNode::globalReadArticleCount,
						NewsReportResponse.TopicLandscapeNode::x,
						NewsReportResponse.TopicLandscapeNode::y,
						NewsReportResponse.TopicLandscapeNode::strong,
						NewsReportResponse.TopicLandscapeNode::familiarity)
				.containsExactly(tuple("ENTITY", null, 2L, 40L, 12.0, 88.0, false, Familiarity.NEW),
						tuple("ENTITY", "ECONOMY", 8L, 126L, 88.0, 12.0, true, Familiarity.FAMILIAR));
		assertThat(response.topicLandscape().getFirst().firstSeenAt().getOffset())
				.isEqualTo(ZoneOffset.ofHours(9));
		assertThat(response.generatedAt().toString()).isEqualTo("2026-09-02T21:00+09:00");

		verify(articleReadRepository).findFirstReadTopics(1L, weeklyFrom, toExclusive);
		verify(userKnowledgeNodeRepository).findEntityLandscapeForNewsReport(
				1L, from, toExclusive, 12);
	}

	@Test
	void 데이터가_없으면_빈_목록과_0을_반환한다() {
		given(articleReadRepository.countRecentReadArticles(any(), any(), any())).willReturn(0L);
		given(articleReadRepository.countRecentReadArticlesBySource(any(), any(), any())).willReturn(List.of());
		given(articleReadRepository.findFirstReadTopics(any(), any(), any())).willReturn(List.of());
		given(userKnowledgeNodeRepository.findEntityLandscapeForNewsReport(any(), any(), any(), anyInt()))
				.willReturn(List.of());

		NewsReportResponse response = newsReportService.getNewsReport(1L);

		assertThat(response.totalReadArticleCount()).isZero();
		assertThat(response.sourceReads()).isEmpty();
		assertThat(response.weeklyTopicTrend()).hasSize(12);
		assertThat(response.weeklyTopicTrend())
				.allSatisfy(week -> {
					assertThat(week.topics()).hasSize(7);
					assertThat(week.topics())
							.extracting(NewsReportResponse.WeeklyTopic::readArticleCount)
							.containsOnly(0L);
				});
		assertThat(response.topicLandscape()).isEmpty();
	}

	@Test
	void 주제_지형_읽기_수가_모두_같으면_중앙에_표시하고_강조하지_않는다() {
		LocalDateTime from = LocalDateTime.of(2026, 6, 2, 0, 0);
		LocalDateTime toExclusive = LocalDateTime.of(2026, 9, 3, 0, 0);
		NewsReportEntityLandscapeRow first = landscapeRow(
				"00000024-0920-4000-8000-000000000001", "HBM", null,
				from, from.plusDays(1), 2, 4);
		NewsReportEntityLandscapeRow second = landscapeRow(
				"00000024-0920-4000-8000-000000000002", "서울", null,
				from, from.plusDays(2), 2, 4);
		given(userKnowledgeNodeRepository.findEntityLandscapeForNewsReport(
				1L, from, toExclusive, 12)).willReturn(List.of(first, second));

		NewsReportResponse response = newsReportService.getNewsReport(1L);

		assertThat(response.topicLandscape())
				.extracting(NewsReportResponse.TopicLandscapeNode::x,
						NewsReportResponse.TopicLandscapeNode::y,
						NewsReportResponse.TopicLandscapeNode::strong)
				.containsExactly(tuple(50.0, 50.0, false), tuple(50.0, 50.0, false));
	}

	@Test
	void 조회_중_예외가_발생하면_NEWS_REPORT_AGGREGATION_FAILED로_변환한다() {
		given(articleReadRepository.countRecentReadArticles(any(), any(), any()))
				.willThrow(new IllegalStateException("database failed"));

		Throwable thrown = catchThrowable(() -> newsReportService.getNewsReport(1L));

		assertThat(thrown).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) thrown).getErrorCode())
				.isEqualTo(NewsReportErrorCode.NEWS_REPORT_AGGREGATION_FAILED);
	}

	private SourceReadCount source(Long organizationId, String organizationName, long count) {
		return new SourceReadCount() {
			@Override
			public Long getOrganizationId() {
				return organizationId;
			}

			@Override
			public String getOrganizationName() {
				return organizationName;
			}

			@Override
			public long getCount() {
				return count;
			}
		};
	}

	private FirstReadTopicRow weeklyRow(LocalDateTime firstReadAt, String topicCode) {
		return new FirstReadTopicRow() {
			@Override
			public LocalDateTime getFirstReadAt() {
				return firstReadAt;
			}

			@Override
			public String getTopicCode() {
				return topicCode;
			}
		};
	}

	private NewsReportEntityLandscapeRow landscapeRow(String nodeId, String label, String topicCode,
			LocalDateTime firstSeenAt, LocalDateTime lastSeenAt,
			long userReadArticleCount, long globalReadArticleCount) {
		return new NewsReportEntityLandscapeRow() {
			@Override
			public String getNodeType() {
				return "ENTITY";
			}

			@Override
			public String getNodeKey() {
				return nodeId;
			}

			@Override
			public String getNodeLabel() {
				return label;
			}

			@Override
			public String getTopicCode() {
				return topicCode;
			}

			@Override
			public long getUserReadArticleCount() {
				return userReadArticleCount;
			}

			@Override
			public long getGlobalReadArticleCount() {
				return globalReadArticleCount;
			}

			@Override
			public LocalDateTime getFirstSeenAt() {
				return firstSeenAt;
			}

			@Override
			public LocalDateTime getLastSeenAt() {
				return lastSeenAt;
			}
		};
	}
}

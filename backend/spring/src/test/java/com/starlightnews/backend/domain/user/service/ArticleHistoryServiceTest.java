package com.starlightnews.backend.domain.user.service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.user.dto.ArticleHistoryResponse;
import com.starlightnews.backend.domain.user.exception.PersonalGraphErrorCode;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository.HistoryRow;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.domain.user.support.ArticleReadCursor;
import com.starlightnews.backend.domain.user.support.GraphReadPeriod;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.ErrorCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageRequest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class ArticleHistoryServiceTest {

	@Mock
	private ArticleReadRepository articleReadRepository;

	@Mock
	private UserArticleFavoriteRepository userArticleFavoriteRepository;

	@InjectMocks
	private ArticleHistoryService articleHistoryService;

	private static final long USER_ID = 1L;

	private HistoryRow row(long articleId, String title, String org, String topicCode,
			LocalDateTime lastReadAt, int clickCount, String summary) {
		return new HistoryRow() {
			@Override
			public Long getArticleId() {
				return articleId;
			}

			@Override
			public String getTitle() {
				return title;
			}

			@Override
			public String getOrganizationName() {
				return org;
			}

			@Override
			public String getTopicCode() {
				return topicCode;
			}

			@Override
			public LocalDateTime getLastReadAt() {
				return lastReadAt;
			}

			@Override
			public int getClickCount() {
				return clickCount;
			}

			@Override
			public String getSummary() {
				return summary;
			}
		};
	}

	private ErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 정상_조회는_열람기록을_최신순으로_토픽명과_북마크와_함께_반환한다() {
		LocalDateTime older = LocalDateTime.of(2026, 8, 30, 9, 0);
		LocalDateTime newer = LocalDateTime.of(2026, 8, 31, 9, 10);
		given(articleReadRepository.findFirstHistoryPage(eq(USER_ID), isNull(), eq(PageRequest.of(0, 3))))
				.willReturn(List.of(
						row(102L, "환율 급등", "연합뉴스", "ECONOMY", newer, 5, null),
						row(101L, "기준금리 동결", "연합뉴스", "ECONOMY", older, 1, "한국은행이 금리를 동결했다.")));
		given(userArticleFavoriteRepository.findFavoritedArticleIds(USER_ID, List.of(102L, 101L)))
				.willReturn(List.of(102L));

		ArticleHistoryResponse response = articleHistoryService.getHistory(USER_ID, null, 2, null);

		assertThat(response.items()).extracting(ArticleHistoryResponse.Item::articleId)
				.containsExactly(102L, 101L);
		assertThat(response.items().get(0).lastReadAt()).isEqualTo(newer.atOffset(ZoneOffset.ofHours(9)));
		assertThat(response.items().get(0).clickCount()).isEqualTo(5);
		assertThat(response.items().get(0).topicName()).isEqualTo("경제");
		assertThat(response.items().get(0).bookmarked()).isTrue();
		assertThat(response.items().get(1).bookmarked()).isFalse();
		assertThat(response.items().get(1).summaryPreview()).isEqualTo("한국은행이 금리를 동결했다.");
		assertThat(response.items().get(0).summaryPreview()).isNull();
		assertThat(response.hasNext()).isFalse();
		assertThat(response.nextCursor()).isNull();
	}

	@Test
	void size보다_한개_더_오면_hasNext_true이고_nextCursor를_만든다() {
		LocalDateTime t1 = LocalDateTime.of(2026, 8, 31, 9, 0);
		LocalDateTime t2 = LocalDateTime.of(2026, 8, 30, 9, 0);
		LocalDateTime t3 = LocalDateTime.of(2026, 8, 29, 9, 0);
		given(articleReadRepository.findFirstHistoryPage(eq(USER_ID), isNull(), eq(PageRequest.of(0, 3))))
				.willReturn(List.of(
						row(1L, "a", "org", "ECONOMY", t1, 1, null),
						row(2L, "b", "org", "ECONOMY", t2, 1, null),
						row(3L, "c", "org", "ECONOMY", t3, 1, null)));
		given(userArticleFavoriteRepository.findFavoritedArticleIds(any(), any())).willReturn(List.of());

		ArticleHistoryResponse response = articleHistoryService.getHistory(USER_ID, null, 2, null);

		assertThat(response.items()).hasSize(2);
		assertThat(response.hasNext()).isTrue();
		ArticleReadCursor decoded = ArticleReadCursor.decode(response.nextCursor());
		assertThat(decoded.articleId()).isEqualTo(2L);
		assertThat(decoded.lastReadAt()).isEqualTo(t2.atOffset(ZoneOffset.ofHours(9)));
	}

	@Test
	void 커서가_있으면_findNextHistoryPage를_topicCode와_함께_호출한다() {
		OffsetDateTime cursorTime = OffsetDateTime.of(2026, 8, 30, 9, 0, 0, 0, ZoneOffset.ofHours(9));
		String rawCursor = new ArticleReadCursor(cursorTime, 102L).encode();
		given(articleReadRepository.findNextHistoryPage(any(), any(), any(), any(), any())).willReturn(List.of());

		articleHistoryService.getHistory(USER_ID, "economy", 20, rawCursor);

		verify(articleReadRepository).findNextHistoryPage(
				eq(USER_ID), eq("ECONOMY"), eq(cursorTime.toLocalDateTime()), eq(102L), eq(PageRequest.of(0, 21)));
	}

	@Test
	void 기간이_있으면_기간용_첫_페이지_쿼리를_호출한다() {
		GraphReadPeriod period = new GraphReadPeriod(LocalDate.of(2026, 9, 1), LocalDate.of(2026, 9, 30));
		given(articleReadRepository.findFirstHistoryPageInPeriod(USER_ID, "ECONOMY",
				period.fromInclusive(), period.toExclusive(), PageRequest.of(0, 21))).willReturn(List.of());

		articleHistoryService.getHistory(USER_ID, "economy", 20, null, period);

		verify(articleReadRepository).findFirstHistoryPageInPeriod(USER_ID, "ECONOMY",
				period.fromInclusive(), period.toExclusive(), PageRequest.of(0, 21));
		verify(articleReadRepository, never()).findFirstHistoryPage(any(), any(), any());
	}

	@Test
	void topicCode가_없으면_null_필터로_조회한다() {
		given(articleReadRepository.findFirstHistoryPage(eq(USER_ID), isNull(), any())).willReturn(List.of());

		articleHistoryService.getHistory(USER_ID, "", 20, null);

		verify(articleReadRepository).findFirstHistoryPage(eq(USER_ID), isNull(), eq(PageRequest.of(0, 21)));
	}

	@Test
	void 잘못된_커서면_INVALID_CURSOR이고_아무것도_조회하지_않는다() {
		Throwable thrown = catchThrowable(() -> articleHistoryService.getHistory(
				USER_ID, null, 20, "!!!not-base64!!!"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
		verifyNoInteractions(articleReadRepository, userArticleFavoriteRepository);
	}

	@Test
	void 잘못된_topicCode면_INVALID_TOPIC_CODE이고_아무것도_조회하지_않는다() {
		Throwable thrown = catchThrowable(() -> articleHistoryService.getHistory(
				USER_ID, "NOT_A_TOPIC", 20, null));

		assertThat(errorCodeOf(thrown)).isEqualTo(PersonalGraphErrorCode.INVALID_TOPIC_CODE);
		verifyNoInteractions(articleReadRepository, userArticleFavoriteRepository);
	}

	@Test
	void 열람기록이_없으면_북마크를_조회하지_않는다() {
		given(articleReadRepository.findFirstHistoryPage(any(), any(), any())).willReturn(List.of());

		ArticleHistoryResponse response = articleHistoryService.getHistory(USER_ID, null, 20, null);

		assertThat(response.items()).isEmpty();
		verify(userArticleFavoriteRepository, never()).findFavoritedArticleIds(any(), any());
	}

	@Test
	void 요약이_120자_넘으면_120자로_자르고_말줄임표를_붙인다() {
		String longSummary = "가".repeat(150);
		given(articleReadRepository.findFirstHistoryPage(any(), any(), any())).willReturn(List.of(
				row(101L, "제목", "연합뉴스", "ECONOMY", LocalDateTime.of(2026, 8, 31, 9, 0), 1, longSummary)));
		given(userArticleFavoriteRepository.findFavoritedArticleIds(any(), any())).willReturn(List.of());

		ArticleHistoryResponse response = articleHistoryService.getHistory(USER_ID, null, 20, null);

		String preview = response.items().get(0).summaryPreview();
		assertThat(preview).hasSize(121).endsWith("…").isEqualTo("가".repeat(120) + "…");
	}
}

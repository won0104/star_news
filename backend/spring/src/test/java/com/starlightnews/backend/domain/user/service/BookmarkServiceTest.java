package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.exception.UserErrorCode;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository.ArticleBookmarkRow;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.domain.user.support.ArticleBookmarkCursor;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.response.CursorResponse;
import com.starlightnews.backend.domain.user.dto.ArticleBookmarkItem;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageRequest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class BookmarkServiceTest {

	private static final long USER_ID = 1L;
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	@Mock
	private UserRepository userRepository;

	@Mock
	private UserArticleFavoriteRepository userArticleFavoriteRepository;

	@InjectMocks
	private BookmarkService bookmarkService;

	@BeforeEach
	void setUpActiveUser() {
		given(userRepository.findById(USER_ID))
				.willReturn(Optional.of(User.create("login", "hash", "nickname")));
	}

	@Test
	void 첫_페이지는_COMPLETED_기사만_size보다_한개_더_조회한다() {
		LocalDateTime newest = LocalDateTime.of(2026, 9, 1, 9, 0);
		LocalDateTime middle = LocalDateTime.of(2026, 8, 31, 9, 0);
		LocalDateTime oldest = LocalDateTime.of(2026, 8, 30, 9, 0);
		given(userArticleFavoriteRepository.findFirstArticleBookmarkPage(
				eq(USER_ID), eq(AnalysisStatus.COMPLETED), eq(PageRequest.of(0, 3))))
				.willReturn(List.of(
						row(103L, "제목3", newest, "요약3", newest),
						row(102L, "제목2", middle, null, middle),
						row(101L, "제목1", oldest, "요약1", oldest)));

		CursorResponse<ArticleBookmarkItem> response =
				bookmarkService.getArticleBookmarks(USER_ID, null, 2);

		assertThat(response.items()).extracting(ArticleBookmarkItem::articleId)
				.containsExactly(103L, 102L);
		assertThat(response.items().get(0).publisher()).isEqualTo("연합뉴스");
		assertThat(response.items().get(0).publishedAt()).isEqualTo(newest.atOffset(KST));
		assertThat(response.items().get(1).summary()).isNull();
		assertThat(response.hasNext()).isTrue();
		assertThat(ArticleBookmarkCursor.decode(response.nextCursor()))
				.isEqualTo(new ArticleBookmarkCursor(middle.atOffset(KST), 102L));
	}

	@Test
	void 다음_페이지는_커서_시각을_KST_DB_시각으로_변환해_조회한다() {
		OffsetDateTime utcCursorTime = OffsetDateTime.of(
				2026, 9, 1, 0, 0, 0, 0, ZoneOffset.UTC);
		String cursor = new ArticleBookmarkCursor(utcCursorTime, 101L).encode();
		given(userArticleFavoriteRepository.findNextArticleBookmarkPage(any(), any(), any(), any(), any()))
				.willReturn(List.of());

		CursorResponse<ArticleBookmarkItem> response =
				bookmarkService.getArticleBookmarks(USER_ID, cursor, 20);

		verify(userArticleFavoriteRepository).findNextArticleBookmarkPage(
				eq(USER_ID),
				eq(AnalysisStatus.COMPLETED),
				eq(LocalDateTime.of(2026, 9, 1, 9, 0)),
				eq(101L),
				eq(PageRequest.of(0, 21)));
		assertThat(response.items()).isEmpty();
		assertThat(response.hasNext()).isFalse();
		assertThat(response.nextCursor()).isNull();
	}

	@Test
	void 사용자가_없으면_USER_NOT_FOUND이고_북마크는_조회하지_않는다() {
		given(userRepository.findById(USER_ID)).willReturn(Optional.empty());

		assertThatThrownBy(() -> bookmarkService.getArticleBookmarks(USER_ID, null, 20))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		verifyNoInteractions(userArticleFavoriteRepository);
	}

	@Test
	void 탈퇴한_사용자도_USER_NOT_FOUND이다() {
		User deletedUser = User.create("deleted", "hash", "nickname");
		deletedUser.markDeleted();
		given(userRepository.findById(USER_ID)).willReturn(Optional.of(deletedUser));

		assertThatThrownBy(() -> bookmarkService.getArticleBookmarks(USER_ID, null, 20))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.USER_NOT_FOUND));
		verifyNoInteractions(userArticleFavoriteRepository);
	}

	@Test
	void 잘못된_커서는_INVALID_CURSOR이고_북마크는_조회하지_않는다() {
		assertThatThrownBy(() -> bookmarkService.getArticleBookmarks(USER_ID, "invalid", 20))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.INVALID_CURSOR));
		verify(userArticleFavoriteRepository, never())
				.findFirstArticleBookmarkPage(any(), any(), any());
		verify(userArticleFavoriteRepository, never())
				.findNextArticleBookmarkPage(any(), any(), any(), any(), any());
	}

	private ArticleBookmarkRow row(long articleId, String title, LocalDateTime publishedAt,
			String summary, LocalDateTime bookmarkedAt) {
		return new ArticleBookmarkRow() {
			@Override
			public Long getArticleId() {
				return articleId;
			}

			@Override
			public String getTitle() {
				return title;
			}

			@Override
			public String getPublisher() {
				return "연합뉴스";
			}

			@Override
			public LocalDateTime getPublishedAt() {
				return publishedAt;
			}

			@Override
			public String getSummary() {
				return summary;
			}

			@Override
			public LocalDateTime getBookmarkedAt() {
				return bookmarkedAt;
			}
		};
	}
}

package com.starlightnews.backend.domain.user.service;

import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.dto.ArticleBookmarkItem;
import com.starlightnews.backend.domain.user.exception.UserErrorCode;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository.ArticleBookmarkRow;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.domain.user.support.ArticleBookmarkCursor;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.response.CursorResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** 로그인 사용자의 기사 및 그래프 Node 북마크를 조회하고 관리한다. */
@Service
@RequiredArgsConstructor
public class BookmarkService {

	/** DB DATETIME(6)은 KST 벽시계로 저장되므로 응답 시각에 +09:00 오프셋을 붙인다. */
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	private final UserRepository userRepository;
	private final UserArticleFavoriteRepository userArticleFavoriteRepository;

	/** 공개 상태인 북마크 기사를 최신 등록순으로 조회한다. */
	@Transactional(readOnly = true)
	public CursorResponse<ArticleBookmarkItem> getArticleBookmarks(long userId, String rawCursor, int size) {
		findActiveUser(userId);
		ArticleBookmarkCursor cursor = (rawCursor == null || rawCursor.isBlank())
				? null : ArticleBookmarkCursor.decode(rawCursor);

		List<ArticleBookmarkRow> rows = (cursor == null)
				? userArticleFavoriteRepository.findFirstArticleBookmarkPage(
						userId, AnalysisStatus.COMPLETED, PageRequest.of(0, size + 1))
				: userArticleFavoriteRepository.findNextArticleBookmarkPage(
						userId,
						AnalysisStatus.COMPLETED,
						cursor.bookmarkedAt().withOffsetSameInstant(KST).toLocalDateTime(),
						cursor.articleId(),
						PageRequest.of(0, size + 1));

		boolean hasNext = rows.size() > size;
		List<ArticleBookmarkRow> page = hasNext ? rows.subList(0, size) : rows;
		List<ArticleBookmarkItem> items = page.stream().map(this::toItem).toList();
		String nextCursor = hasNext ? encodeCursor(page.get(page.size() - 1)) : null;

		return CursorResponse.of(items, hasNext, nextCursor);
	}

	private User findActiveUser(long userId) {
		return userRepository.findById(userId)
				.filter(user -> !user.isDeleted())
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}

	private ArticleBookmarkItem toItem(ArticleBookmarkRow row) {
		return new ArticleBookmarkItem(
				row.getArticleId(),
				row.getTitle(),
				row.getPublisher(),
				row.getPublishedAt().atOffset(KST),
				row.getSummary(),
				row.getBookmarkedAt().atOffset(KST));
	}

	private String encodeCursor(ArticleBookmarkRow row) {
		return new ArticleBookmarkCursor(
				row.getBookmarkedAt().atOffset(KST), row.getArticleId()).encode();
	}
}

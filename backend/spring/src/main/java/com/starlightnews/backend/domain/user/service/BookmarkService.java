package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.domain.UserArticleFavorite;
import com.starlightnews.backend.domain.user.domain.UserArticleFavoriteId;
import com.starlightnews.backend.domain.user.dto.ArticleBookmarkItem;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksRequest;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksRequest.ArticleBookmarkChange;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksResponse;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksResponse.ArticleBookmarkResult;
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
	private final ArticleRepository articleRepository;
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

	/** 요청에 포함된 기사만 목표 북마크 상태로 변경한다. */
	@Transactional
	public UpdateArticleBookmarksResponse updateArticleBookmarks(
			long userId, UpdateArticleBookmarksRequest request) {
		List<ArticleBookmarkChange> changes = request.changes();
		validateChanges(changes);
		findActiveUser(userId);

		Set<Long> requestedArticleIds = changes.stream()
				.map(ArticleBookmarkChange::articleId)
				.collect(Collectors.toCollection(LinkedHashSet::new));
		Set<Long> articlesToBookmark = changes.stream()
				.filter(change -> change.bookmarked())
				.map(ArticleBookmarkChange::articleId)
				.collect(Collectors.toSet());
		validateArticlesToBookmark(articlesToBookmark);

		Set<Long> currentlyBookmarked = new HashSet<>(
				userArticleFavoriteRepository.findFavoritedArticleIds(userId, requestedArticleIds));
		LocalDateTime favoritedAt = LocalDateTime.now(KST);
		List<UserArticleFavorite> favoritesToAdd = changes.stream()
				.filter(ArticleBookmarkChange::bookmarked)
				.filter(change -> !currentlyBookmarked.contains(change.articleId()))
				.map(change -> new UserArticleFavorite(
						new UserArticleFavoriteId(userId, change.articleId()), favoritedAt))
				.toList();
		List<Long> articleIdsToRemove = changes.stream()
				.filter(change -> !change.bookmarked())
				.map(ArticleBookmarkChange::articleId)
				.filter(currentlyBookmarked::contains)
				.toList();

		if (!favoritesToAdd.isEmpty()) {
			userArticleFavoriteRepository.saveAll(favoritesToAdd);
		}
		if (!articleIdsToRemove.isEmpty()) {
			userArticleFavoriteRepository.deleteByUserIdAndArticleIds(userId, articleIdsToRemove);
		}

		List<ArticleBookmarkResult> results = changes.stream()
				.map(change -> new ArticleBookmarkResult(change.articleId(), change.bookmarked()))
				.toList();
		return new UpdateArticleBookmarksResponse(results);
	}

	private void validateChanges(List<ArticleBookmarkChange> changes) {
		if (changes.isEmpty()) {
			throw new BusinessException(UserErrorCode.EMPTY_CHANGES);
		}

		Set<Long> articleIds = new HashSet<>();
		for (ArticleBookmarkChange change : changes) {
			if (!articleIds.add(change.articleId())) {
				throw new BusinessException(UserErrorCode.DUPLICATED_ARTICLE_CHANGE);
			}
		}
	}

	private void validateArticlesToBookmark(Set<Long> articleIds) {
		if (articleIds.isEmpty()) {
			return;
		}

		Set<Long> availableArticleIds = Set.copyOf(
				articleRepository.findArticleIdsByIdInAndAnalysisStatus(
						articleIds, AnalysisStatus.COMPLETED));
		if (!availableArticleIds.containsAll(articleIds)) {
			throw new BusinessException(UserErrorCode.ARTICLE_NOT_FOUND);
		}
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

package com.starlightnews.backend.domain.user.service;

import java.time.ZoneOffset;
import java.util.List;
import java.util.Set;

import com.starlightnews.backend.domain.user.dto.ArticleHistoryResponse;
import com.starlightnews.backend.domain.user.dto.ArticleHistoryResponse.Item;
import com.starlightnews.backend.domain.user.exception.PersonalGraphErrorCode;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository.HistoryRow;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.domain.user.support.ArticleReadCursor;
import com.starlightnews.backend.domain.user.support.GraphReadPeriod;
import com.starlightnews.backend.domain.user.support.SummaryPreview;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 사용자의 전체 기사 열람 기록을 최근 읽은 순으로 조회한다. Neo4j 는 관여하지 않는, 순수 MySQL(article_reads) 조회다.
 */
@Service
@RequiredArgsConstructor
public class ArticleHistoryService {

	/** DB DATETIME(6) 은 KST 벽시계로 저장되므로 응답 시각에 +09:00 오프셋을 붙인다. */
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	private final ArticleReadRepository articleReadRepository;
	private final UserArticleFavoriteRepository userArticleFavoriteRepository;

	@Transactional(readOnly = true)
	public ArticleHistoryResponse getHistory(Long userId, String rawTopicCode, int size, String rawCursor) {
		return getHistory(userId, rawTopicCode, size, rawCursor, null);
	}

	@Transactional(readOnly = true)
	public ArticleHistoryResponse getHistory(Long userId, String rawTopicCode, int size, String rawCursor,
			GraphReadPeriod period) {

		String topicCode = resolveTopicCode(rawTopicCode);

		ArticleReadCursor cursor = (rawCursor == null || rawCursor.isBlank())
				? null : ArticleReadCursor.decode(rawCursor);

		List<HistoryRow> rows;
		if (period == null) {
			rows = (cursor == null)
					? articleReadRepository.findFirstHistoryPage(userId, topicCode, PageRequest.of(0, size + 1))
					: articleReadRepository.findNextHistoryPage(userId, topicCode,
							cursor.lastReadAt().toLocalDateTime(), cursor.articleId(), PageRequest.of(0, size + 1));
		} else {
			rows = (cursor == null)
					? articleReadRepository.findFirstHistoryPageInPeriod(userId, topicCode,
							period.fromInclusive(), period.toExclusive(), PageRequest.of(0, size + 1))
					: articleReadRepository.findNextHistoryPageInPeriod(userId, topicCode,
							period.fromInclusive(), period.toExclusive(),
							cursor.lastReadAt().toLocalDateTime(), cursor.articleId(), PageRequest.of(0, size + 1));
		}

		boolean hasNext = rows.size() > size;
		List<HistoryRow> page = hasNext ? rows.subList(0, size) : rows;

		if (page.isEmpty()) {
			return new ArticleHistoryResponse(List.of(), false, null);
		}

		Set<Long> bookmarkedIds = Set.copyOf(userArticleFavoriteRepository.findFavoritedArticleIds(
				userId, page.stream().map(HistoryRow::getArticleId).toList()));

		List<Item> items = page.stream().map(row -> toItem(row, bookmarkedIds)).toList();
		String nextCursor = hasNext ? encodeCursor(page.get(page.size() - 1)) : null;

		return new ArticleHistoryResponse(items, hasNext, nextCursor);
	}

	private String resolveTopicCode(String rawTopicCode) {
		if (rawTopicCode == null || rawTopicCode.isBlank()) {
			return null;
		}
		return TopicCode.from(rawTopicCode)
				.orElseThrow(() -> new BusinessException(PersonalGraphErrorCode.INVALID_TOPIC_CODE))
				.name();
	}

	private Item toItem(HistoryRow row, Set<Long> bookmarkedIds) {
		String topicName = TopicCode.from(row.getTopicCode()).map(TopicCode::labelKo).orElse(null);
		return new Item(
				row.getArticleId(),
				row.getTitle(),
				row.getOrganizationName(),
				row.getTopicCode(),
				topicName,
				row.getLastReadAt().atOffset(KST),
				row.getClickCount(),
				SummaryPreview.truncate(row.getSummary()),
				bookmarkedIds.contains(row.getArticleId()));
	}

	private String encodeCursor(HistoryRow row) {
		return new ArticleReadCursor(row.getLastReadAt().atOffset(KST), row.getArticleId()).encode();
	}
}

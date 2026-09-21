package com.starlightnews.backend.domain.user.service;

import java.time.ZoneOffset;
import java.util.List;
import java.util.Set;
import java.util.function.Supplier;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.graph.support.ArticleRelation;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.domain.user.dto.PersonalNodeArticlesResponse;
import com.starlightnews.backend.domain.user.dto.PersonalNodeArticlesResponse.Item;
import com.starlightnews.backend.domain.user.dto.PersonalNodeArticlesResponse.NodeSummary;
import com.starlightnews.backend.domain.user.exception.PersonalGraphErrorCode;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository.ReadArticleRow;
import com.starlightnews.backend.domain.user.repository.PersonalNodeArticleRepository;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.domain.user.support.ArticleReadCursor;
import com.starlightnews.backend.domain.user.support.GraphReadPeriod;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 개인 그래프에서 선택한 Node 와 관련된 기사 중, 사용자가 실제로 읽은 기사만 조회한다.
 * 련 기사 후보는 Neo4j 에서·실제 정렬과 페이지네이션은
 * MySQL article_reads(사용자가 읽은 시각 기준)에서 담당한다.
 */
@Service
@RequiredArgsConstructor
public class PersonalNodeArticleService {

	/** DB DATETIME(6) 은 KST 벽시계로 저장되므로 응답 시각에 +09:00 오프셋을 붙인다. */
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	/** summaryPreview 로 자를 최대 글자 수. */
	private static final int SUMMARY_PREVIEW_LENGTH = 120;

	private final UserKnowledgeNodeRepository userKnowledgeNodeRepository;
	private final PersonalNodeArticleRepository personalNodeArticleRepository;
	private final ArticleReadRepository articleReadRepository;
	private final UserArticleFavoriteRepository userArticleFavoriteRepository;

	@Transactional(readOnly = true)
	public PersonalNodeArticlesResponse getReadArticles(Long userId, NodeType nodeType, String nodeKey,
			int size, String rawCursor) {
		return getReadArticles(userId, nodeType, nodeKey, size, rawCursor, null);
	}

	@Transactional(readOnly = true)
	public PersonalNodeArticlesResponse getReadArticles(Long userId, NodeType nodeType, String nodeKey,
			int size, String rawCursor, GraphReadPeriod period) {

		ArticleReadCursor cursor = (rawCursor == null || rawCursor.isBlank())
				? null : ArticleReadCursor.decode(rawCursor);

		UserKnowledgeNode node = userKnowledgeNodeRepository
				.findById(new UserKnowledgeNodeId(userId, nodeType, nodeKey))
				.orElseThrow(() -> new BusinessException(PersonalGraphErrorCode.NODE_NOT_ACQUIRED));

		ArticleRelation relation = ArticleRelation.forNodeType(nodeType)
				.orElseThrow(() -> new BusinessException(GraphErrorCode.INVALID_NODE_TYPE));

		NodeSummary nodeSummary = new NodeSummary(nodeType.name(), nodeKey, node.getNodeLabel());

		List<Long> candidateIds = fromNeo4j(
				() -> personalNodeArticleRepository.findRelatedArticleIds(relation, nodeKey));
		if (candidateIds.isEmpty()) {
			return new PersonalNodeArticlesResponse(nodeSummary, List.of(), false, null);
		}

		List<ReadArticleRow> rows;
		if (period == null) {
			rows = (cursor == null)
					? articleReadRepository.findFirstReadPage(userId, candidateIds, PageRequest.of(0, size + 1))
					: articleReadRepository.findNextReadPage(userId, candidateIds,
							cursor.lastReadAt().toLocalDateTime(), cursor.articleId(), PageRequest.of(0, size + 1));
		} else {
			rows = (cursor == null)
					? articleReadRepository.findFirstReadPageInPeriod(userId, candidateIds,
							period.fromInclusive(), period.toExclusive(), PageRequest.of(0, size + 1))
					: articleReadRepository.findNextReadPageInPeriod(userId, candidateIds,
							period.fromInclusive(), period.toExclusive(),
							cursor.lastReadAt().toLocalDateTime(), cursor.articleId(), PageRequest.of(0, size + 1));
		}

		boolean hasNext = rows.size() > size;
		List<ReadArticleRow> page = hasNext ? rows.subList(0, size) : rows;

		if (page.isEmpty()) {
			return new PersonalNodeArticlesResponse(nodeSummary, List.of(), false, null);
		}

		Set<Long> bookmarkedIds = Set.copyOf(userArticleFavoriteRepository.findFavoritedArticleIds(
				userId, page.stream().map(ReadArticleRow::getArticleId).toList()));

		List<Item> items = page.stream().map(row -> toItem(row, bookmarkedIds)).toList();
		String nextCursor = hasNext ? encodeCursor(page.get(page.size() - 1)) : null;

		return new PersonalNodeArticlesResponse(nodeSummary, items, hasNext, nextCursor);
	}

	private Item toItem(ReadArticleRow row, Set<Long> bookmarkedIds) {
		return new Item(
				row.getArticleId(),
				row.getTitle(),
				row.getOrganizationName(),
				row.getTopicCode(),
				row.getLastReadAt().atOffset(KST),
				summaryPreview(row.getSummary()),
				bookmarkedIds.contains(row.getArticleId()));
	}

	private static String summaryPreview(String summary) {
		if (summary == null || summary.isBlank()) {
			return null;
		}
		if (summary.length() <= SUMMARY_PREVIEW_LENGTH) {
			return summary;
		}
		return summary.substring(0, SUMMARY_PREVIEW_LENGTH) + "…";
	}

	private String encodeCursor(ReadArticleRow row) {
		return new ArticleReadCursor(row.getLastReadAt().atOffset(KST), row.getArticleId()).encode();
	}

	private <T> T fromNeo4j(Supplier<T> call) {
		try {
			return call.get();
		} catch (RuntimeException exception) {
			throw new BusinessException(CommonErrorCode.INTERNAL_SERVER_ERROR);
		}
	}
}

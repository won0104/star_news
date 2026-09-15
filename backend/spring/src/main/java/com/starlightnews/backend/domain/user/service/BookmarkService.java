package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.HashSet;
import java.util.HashMap;
import java.util.EnumSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.domain.UserArticleFavorite;
import com.starlightnews.backend.domain.user.domain.UserArticleFavoriteId;
import com.starlightnews.backend.domain.user.domain.UserNodeFavorite;
import com.starlightnews.backend.domain.user.domain.UserNodeFavoriteId;
import com.starlightnews.backend.domain.user.dto.ArticleBookmarkItem;
import com.starlightnews.backend.domain.user.dto.NodeBookmarkItem;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksRequest;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksRequest.ArticleBookmarkChange;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksResponse;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksResponse.ArticleBookmarkResult;
import com.starlightnews.backend.domain.user.dto.UpdateNodeBookmarksRequest;
import com.starlightnews.backend.domain.user.dto.UpdateNodeBookmarksRequest.NodeBookmarkChange;
import com.starlightnews.backend.domain.user.dto.UpdateNodeBookmarksResponse;
import com.starlightnews.backend.domain.user.dto.UpdateNodeBookmarksResponse.NodeBookmarkResult;
import com.starlightnews.backend.domain.user.exception.UserErrorCode;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository.ArticleBookmarkRow;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.domain.user.repository.NodeName;
import com.starlightnews.backend.domain.user.repository.NodeSnapshotRepository;
import com.starlightnews.backend.domain.user.repository.UserNodeFavoriteRepository;
import com.starlightnews.backend.domain.user.repository.UserNodeFavoriteRepository.NodeFavoriteRow;
import com.starlightnews.backend.domain.user.support.ArticleBookmarkCursor;
import com.starlightnews.backend.domain.user.support.NodeBookmarkCursor;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.NodeType;
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
	private static final Set<NodeType> FAVORITE_NODE_TYPES = EnumSet.of(
			NodeType.EVENT, NodeType.STORY, NodeType.ENTITY, NodeType.STATEMENT);

	private final UserRepository userRepository;
	private final ArticleRepository articleRepository;
	private final UserArticleFavoriteRepository userArticleFavoriteRepository;
	private final UserNodeFavoriteRepository userNodeFavoriteRepository;
	private final NodeSnapshotRepository nodeSnapshotRepository;

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

	/** 즐겨찾기 가능한 그래프 Node를 최신 등록순으로 조회한다. */
	@Transactional(readOnly = true)
	public CursorResponse<NodeBookmarkItem> getNodeBookmarks(
			long userId, String rawNodeType, String rawCursor, int size) {
		NodeType nodeTypeFilter = resolveFavoriteNodeType(rawNodeType);
		findActiveUser(userId);
		NodeBookmarkCursor cursor = (rawCursor == null || rawCursor.isBlank())
				? null : decodeNodeCursor(rawCursor);
		List<String> nodeTypes = nodeTypeFilter == null
				? FAVORITE_NODE_TYPES.stream().map(Enum::name).sorted().toList()
				: List.of(nodeTypeFilter.name());

		List<NodeFavoriteRow> rows = cursor == null
				? userNodeFavoriteRepository.findFirstNodeFavoritePage(
						userId, nodeTypes, PageRequest.of(0, size + 1))
				: userNodeFavoriteRepository.findNextNodeFavoritePage(
						userId,
						nodeTypes,
						cursor.bookmarkedAt().withOffsetSameInstant(KST).toLocalDateTime(),
						cursor.nodeType().name(),
						cursor.nodeId(),
						PageRequest.of(0, size + 1));

		boolean hasNext = rows.size() > size;
		List<NodeFavoriteRow> page = hasNext ? rows.subList(0, size) : rows;
		Map<NodeReference, String> names = findNodeNames(page);
		List<NodeBookmarkItem> items = page.stream()
				.map(row -> toNodeItem(row, names))
				.toList();
		String nextCursor = hasNext ? encodeNodeCursor(page.get(page.size() - 1)) : null;

		return CursorResponse.of(items, hasNext, nextCursor);
	}

	/** 요청에 포함된 그래프 Node만 목표 즐겨찾기 상태로 변경한다. */
	@Transactional
	public UpdateNodeBookmarksResponse updateNodeBookmarks(
			long userId, UpdateNodeBookmarksRequest request) {
		List<ParsedNodeChange> changes = parseNodeChanges(request.changes());
		findActiveUser(userId);
		validateNodesExist(changes);

		List<UserNodeFavoriteId> requestedIds = changes.stream()
				.map(change -> new UserNodeFavoriteId(userId, change.nodeType(), change.nodeId()))
				.toList();
		Set<UserNodeFavoriteId> currentlyBookmarked = userNodeFavoriteRepository.findAllById(requestedIds)
				.stream()
				.map(UserNodeFavorite::getId)
				.collect(Collectors.toSet());
		LocalDateTime favoritedAt = LocalDateTime.now(KST);
		List<UserNodeFavorite> favoritesToAdd = changes.stream()
				.filter(ParsedNodeChange::bookmarked)
				.map(change -> new UserNodeFavoriteId(userId, change.nodeType(), change.nodeId()))
				.filter(id -> !currentlyBookmarked.contains(id))
				.map(id -> new UserNodeFavorite(id, favoritedAt))
				.toList();
		List<UserNodeFavoriteId> favoriteIdsToRemove = changes.stream()
				.filter(change -> !change.bookmarked())
				.map(change -> new UserNodeFavoriteId(userId, change.nodeType(), change.nodeId()))
				.filter(currentlyBookmarked::contains)
				.toList();

		if (!favoritesToAdd.isEmpty()) {
			userNodeFavoriteRepository.saveAll(favoritesToAdd);
		}
		if (!favoriteIdsToRemove.isEmpty()) {
			userNodeFavoriteRepository.deleteAllByIdInBatch(favoriteIdsToRemove);
		}

		List<NodeBookmarkResult> results = changes.stream()
				.map(change -> new NodeBookmarkResult(
						change.nodeType(), change.nodeId(), change.bookmarked()))
				.toList();
		return new UpdateNodeBookmarksResponse(results);
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

	private NodeType resolveFavoriteNodeType(String rawNodeType) {
		if (rawNodeType == null || rawNodeType.isBlank()) {
			return null;
		}

		NodeType nodeType = NodeType.from(rawNodeType)
				.orElseThrow(() -> new BusinessException(GraphErrorCode.INVALID_NODE_TYPE));
		if (!FAVORITE_NODE_TYPES.contains(nodeType)) {
			throw new BusinessException(GraphErrorCode.INVALID_NODE_TYPE);
		}
		return nodeType;
	}

	private List<ParsedNodeChange> parseNodeChanges(List<NodeBookmarkChange> rawChanges) {
		if (rawChanges.isEmpty()) {
			throw new BusinessException(UserErrorCode.EMPTY_CHANGES);
		}

		Set<NodeReference> distinctNodes = new HashSet<>();
		List<ParsedNodeChange> changes = rawChanges.stream()
				.map(change -> new ParsedNodeChange(
						resolveFavoriteNodeType(change.nodeType()),
						change.nodeId().strip(),
						change.bookmarked()))
				.toList();
		for (ParsedNodeChange change : changes) {
			NodeReference node = new NodeReference(change.nodeType(), change.nodeId());
			if (!distinctNodes.add(node)) {
				throw new BusinessException(UserErrorCode.DUPLICATED_NODE_CHANGE);
			}
		}
		return changes;
	}

	private void validateNodesExist(List<ParsedNodeChange> changes) {
		Set<NodeReference> requestedNodes = changes.stream()
				.map(change -> new NodeReference(change.nodeType(), change.nodeId()))
				.collect(Collectors.toSet());
		Map<NodeType, List<String>> idsByType = changes.stream()
				.collect(Collectors.groupingBy(
						ParsedNodeChange::nodeType,
						() -> new java.util.EnumMap<>(NodeType.class),
						Collectors.mapping(ParsedNodeChange::nodeId, Collectors.toList())));
		Set<NodeReference> foundNodes = new HashSet<>();

		try {
			for (Map.Entry<NodeType, List<String>> entry : idsByType.entrySet()) {
				for (NodeName node : nodeSnapshotRepository.findNames(entry.getKey(), entry.getValue())) {
					foundNodes.add(new NodeReference(entry.getKey(), node.nodeId()));
				}
			}
		} catch (RuntimeException exception) {
			throw new BusinessException(GraphErrorCode.GRAPH_NODE_QUERY_FAILED);
		}

		if (!foundNodes.equals(requestedNodes)) {
			throw new BusinessException(UserErrorCode.NODE_NOT_FOUND);
		}
	}

	private NodeBookmarkCursor decodeNodeCursor(String rawCursor) {
		NodeBookmarkCursor cursor = NodeBookmarkCursor.decode(rawCursor);
		if (!FAVORITE_NODE_TYPES.contains(cursor.nodeType())) {
			throw new BusinessException(GraphErrorCode.INVALID_CURSOR);
		}
		return cursor;
	}

	private Map<NodeReference, String> findNodeNames(List<NodeFavoriteRow> rows) {
		Map<NodeType, List<String>> idsByType = rows.stream()
				.collect(Collectors.groupingBy(
						row -> parseStoredNodeType(row.getNodeType()),
						() -> new java.util.EnumMap<>(NodeType.class),
						Collectors.mapping(NodeFavoriteRow::getNodeId, Collectors.toList())));
		Map<NodeReference, String> names = new HashMap<>();

		try {
			for (Map.Entry<NodeType, List<String>> entry : idsByType.entrySet()) {
				for (NodeName node : nodeSnapshotRepository.findNames(entry.getKey(), entry.getValue())) {
					names.put(new NodeReference(entry.getKey(), node.nodeId()), node.name());
				}
			}
		} catch (RuntimeException exception) {
			throw new BusinessException(GraphErrorCode.GRAPH_NODE_QUERY_FAILED);
		}

		if (names.size() != rows.size()) {
			throw new BusinessException(GraphErrorCode.GRAPH_NODE_QUERY_FAILED);
		}
		return names;
	}

	private NodeBookmarkItem toNodeItem(NodeFavoriteRow row, Map<NodeReference, String> names) {
		NodeType nodeType = parseStoredNodeType(row.getNodeType());
		String name = names.get(new NodeReference(nodeType, row.getNodeId()));
		return new NodeBookmarkItem(
				nodeType, row.getNodeId(), name, row.getBookmarkedAt().atOffset(KST));
	}

	private NodeType parseStoredNodeType(String storedNodeType) {
		return NodeType.from(storedNodeType)
				.filter(FAVORITE_NODE_TYPES::contains)
				.orElseThrow(() -> new BusinessException(GraphErrorCode.GRAPH_NODE_QUERY_FAILED));
	}

	private String encodeNodeCursor(NodeFavoriteRow row) {
		return new NodeBookmarkCursor(
				row.getBookmarkedAt().atOffset(KST),
				parseStoredNodeType(row.getNodeType()),
				row.getNodeId())
				.encode();
	}

	private record NodeReference(NodeType nodeType, String nodeId) {
	}

	private record ParsedNodeChange(NodeType nodeType, String nodeId, boolean bookmarked) {
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

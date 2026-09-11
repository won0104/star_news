package com.starlightnews.backend.domain.graph.service;

import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Supplier;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.graph.dto.RelatedArticlesResponse;
import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.graph.repository.RelatedArticleRef;
import com.starlightnews.backend.domain.graph.repository.RelatedArticleRepository;
import com.starlightnews.backend.domain.graph.support.ArticleCursor;
import com.starlightnews.backend.domain.graph.support.ArticleRelation;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class GraphArticleService {

	/** DB DATETIME(6) 은 KST 벽시계로 저장되므로 응답 시 +09:00 오프셋을 붙인다. */
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	private final RelatedArticleRepository relatedArticleRepository;
	private final ArticleRepository articleRepository;
	private final UserArticleFavoriteRepository userArticleFavoriteRepository;

	/**
	 * 노드와 연결된 기사 목록을 최신 발행 순으로 조회한다.
	 * Neo4j 에서 관련 Article ID·정렬을, MySQL 에서 화면 정보와 북마크 여부를 조합한다.
	 * userId 가 null(비로그인)이면 bookmarked 는 항상 false 다.
	 */
	@Transactional(readOnly = true)
	public RelatedArticlesResponse getRelatedArticles(NodeType nodeType, String nodeKey, int size,
			String rawCursor, Long userId) {

		ArticleRelation relation = ArticleRelation.forNodeType(nodeType)
				.orElseThrow(() -> new BusinessException(GraphErrorCode.INVALID_NODE_TYPE));

		ArticleCursor cursor = (rawCursor == null || rawCursor.isBlank())
				? null : ArticleCursor.decode(rawCursor);

		if (!fromNeo4j(() -> relatedArticleRepository.existsNode(relation, nodeKey))) {
			throw new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND);
		}

		long totalCount = fromNeo4j(() -> relatedArticleRepository.countRelatedArticles(relation, nodeKey));
		List<RelatedArticleRef> refs = fromNeo4j(
				() -> relatedArticleRepository.findRefs(relation, nodeKey, cursor, size + 1));

		boolean hasNext = refs.size() > size;
		List<RelatedArticleRef> page = hasNext ? refs.subList(0, size) : refs;

		List<RelatedArticlesResponse.Item> items = toItems(page, userId);
		String nextCursor = hasNext ? encodeCursor(page.get(page.size() - 1)) : null;

		return new RelatedArticlesResponse(items, totalCount, items.size(), hasNext, nextCursor);
	}

	private List<RelatedArticlesResponse.Item> toItems(List<RelatedArticleRef> page, Long userId) {
		if (page.isEmpty()) {
			return List.of();
		}

		List<Long> articleIds = page.stream().map(RelatedArticleRef::articleId).toList();

		Map<Long, Article> articlesById = articleRepository
				.findAllWithOrganizationByArticleIdIn(articleIds).stream()
				.collect(Collectors.toMap(Article::getArticleId, article -> article));

		Set<Long> bookmarkedIds = (userId == null)
				? Set.of()
				: Set.copyOf(userArticleFavoriteRepository.findFavoritedArticleIds(userId, articleIds));

		List<RelatedArticlesResponse.Item> items = new ArrayList<>(page.size());
		for (RelatedArticleRef ref : page) {
			Article article = articlesById.get(ref.articleId());
			if (article == null) {
				continue; // Neo4j 에는 있으나 MySQL 에 없는 기사는 건너뛴다
			}
			items.add(new RelatedArticlesResponse.Item(
					article.getArticleId(),
					article.getTitle(),
					article.getOrganization().getName(),
					article.getPublishedAt().atOffset(KST),
					bookmarkedIds.contains(article.getArticleId())));
		}
		return items;
	}

	private String encodeCursor(RelatedArticleRef ref) {
		return new ArticleCursor(ref.publishedAt(), ref.articleId()).encode();
	}

	private <T> T fromNeo4j(Supplier<T> call) {
		try {
			return call.get();
		} catch (RuntimeException exception) {
			throw new BusinessException(GraphErrorCode.GRAPH_NODE_QUERY_FAILED);
		}
	}
}

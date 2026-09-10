package com.starlightnews.backend.domain.graph.service;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.domain.NewsOrganization;
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
import com.starlightnews.backend.global.error.ErrorCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class GraphArticleServiceTest {

	@Mock
	private RelatedArticleRepository relatedArticleRepository;

	@Mock
	private ArticleRepository articleRepository;

	@Mock
	private UserArticleFavoriteRepository userArticleFavoriteRepository;

	@InjectMocks
	private GraphArticleService graphArticleService;

	private static final String NODE_KEY = "00000020-0920-4000-8000-000000000001";

	private RelatedArticleRef ref(long articleId, LocalDateTime publishedAt) {
		return new RelatedArticleRef(articleId, publishedAt.atOffset(ZoneOffset.ofHours(9)));
	}

	private Article article(long articleId, String title, String org, LocalDateTime publishedAt) {
		Article article = new Article(title, publishedAt, new NewsOrganization(org));
		ReflectionTestUtils.setField(article, "articleId", articleId);
		return article;
	}

	private ErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 정상_조회는_Neo4j_순서대로_MySQL_정보와_북마크를_조합한다() {
		LocalDateTime t1 = LocalDateTime.of(2024, 1, 12, 9, 0);
		LocalDateTime t2 = LocalDateTime.of(2024, 1, 11, 9, 0);
		given(relatedArticleRepository.existsNode(ArticleRelation.EVENT, NODE_KEY)).willReturn(true);
		given(relatedArticleRepository.countRelatedArticles(ArticleRelation.EVENT, NODE_KEY)).willReturn(2L);
		given(relatedArticleRepository.findRefs(ArticleRelation.EVENT, NODE_KEY, null, 3))
				.willReturn(List.of(ref(101L, t1), ref(102L, t2)));
		given(articleRepository.findAllWithOrganizationByArticleIdIn(List.of(101L, 102L)))
				.willReturn(List.of(article(102L, "제목2", "머니S", t2), article(101L, "제목1", "연합뉴스", t1)));
		given(userArticleFavoriteRepository.findFavoritedArticleIds(1L, List.of(101L, 102L)))
				.willReturn(List.of(102L));

		RelatedArticlesResponse response = graphArticleService.getRelatedArticles(
				NodeType.EVENT, NODE_KEY, 2, null, 1L);

		assertThat(response.articles()).extracting(RelatedArticlesResponse.Item::articleId)
				.containsExactly(101L, 102L); // Neo4j 정렬 순서 유지
		assertThat(response.articles().get(0).title()).isEqualTo("제목1");
		assertThat(response.articles().get(0).organizationName()).isEqualTo("연합뉴스");
		assertThat(response.articles().get(0).publishedAt())
				.isEqualTo(OffsetDateTime.of(2024, 1, 12, 9, 0, 0, 0, ZoneOffset.ofHours(9)));
		assertThat(response.articles().get(0).bookmarked()).isFalse();
		assertThat(response.articles().get(1).bookmarked()).isTrue();
		assertThat(response.totalCount()).isEqualTo(2L);
		assertThat(response.returnedCount()).isEqualTo(2);
		assertThat(response.hasNext()).isFalse();
		assertThat(response.nextCursor()).isNull();
	}

	@Test
	void size보다_한_개_더_오면_hasNext_true이고_nextCursor를_만든다() {
		LocalDateTime t1 = LocalDateTime.of(2024, 1, 13, 9, 0);
		LocalDateTime t2 = LocalDateTime.of(2024, 1, 12, 9, 0);
		LocalDateTime t3 = LocalDateTime.of(2024, 1, 11, 9, 0);
		given(relatedArticleRepository.existsNode(any(), any())).willReturn(true);
		given(relatedArticleRepository.countRelatedArticles(any(), any())).willReturn(5L);
		given(relatedArticleRepository.findRefs(eq(ArticleRelation.EVENT), eq(NODE_KEY), eq(null), eq(3)))
				.willReturn(List.of(ref(101L, t1), ref(102L, t2), ref(103L, t3)));
		given(articleRepository.findAllWithOrganizationByArticleIdIn(List.of(101L, 102L)))
				.willReturn(List.of(article(101L, "a", "o", t1), article(102L, "b", "o", t2)));

		RelatedArticlesResponse response = graphArticleService.getRelatedArticles(
				NodeType.EVENT, NODE_KEY, 2, null, null);

		assertThat(response.articles()).hasSize(2);
		assertThat(response.hasNext()).isTrue();
		ArticleCursor decoded = ArticleCursor.decode(response.nextCursor());
		assertThat(decoded.articleId()).isEqualTo(102L);
		assertThat(decoded.publishedAt()).isEqualTo(t2.atOffset(ZoneOffset.ofHours(9)));
	}

	@Test
	void 커서_문자열이_있으면_디코딩해서_repo에_전달한다() {
		String rawCursor = new ArticleCursor(
				LocalDateTime.of(2024, 1, 12, 9, 0).atOffset(ZoneOffset.ofHours(9)), 102L).encode();
		given(relatedArticleRepository.existsNode(any(), any())).willReturn(true);
		given(relatedArticleRepository.countRelatedArticles(any(), any())).willReturn(1L);
		given(relatedArticleRepository.findRefs(any(), any(), any(ArticleCursor.class), anyInt()))
				.willReturn(List.of());

		graphArticleService.getRelatedArticles(NodeType.EVENT, NODE_KEY, 2, rawCursor, null);

		verify(relatedArticleRepository).findRefs(eq(ArticleRelation.EVENT), eq(NODE_KEY),
				eq(new ArticleCursor(LocalDateTime.of(2024, 1, 12, 9, 0).atOffset(ZoneOffset.ofHours(9)), 102L)),
				eq(3));
	}

	@Test
	void 잘못된_커서면_INVALID_CURSOR이고_Neo4j를_건드리지_않는다() {
		Throwable thrown = catchThrowable(() -> graphArticleService.getRelatedArticles(
				NodeType.EVENT, NODE_KEY, 2, "!!!not-base64!!!", null));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
		verifyNoInteractions(relatedArticleRepository, articleRepository, userArticleFavoriteRepository);
	}

	@Test
	void 관련_기사_조회_대상이_아닌_nodeType이면_INVALID_NODE_TYPE() {
		Throwable thrown = catchThrowable(() -> graphArticleService.getRelatedArticles(
				NodeType.STORY, NODE_KEY, 2, null, null));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_NODE_TYPE);
		verifyNoInteractions(relatedArticleRepository);
	}

	@Test
	void 노드가_없으면_RESOURCE_NOT_FOUND이고_count는_호출하지_않는다() {
		given(relatedArticleRepository.existsNode(ArticleRelation.EVENT, NODE_KEY)).willReturn(false);

		Throwable thrown = catchThrowable(() -> graphArticleService.getRelatedArticles(
				NodeType.EVENT, NODE_KEY, 2, null, null));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.RESOURCE_NOT_FOUND);
		verify(relatedArticleRepository, never()).countRelatedArticles(any(), any());
		verify(relatedArticleRepository, never()).findRefs(any(), any(), any(), anyInt());
	}

	@Test
	void Neo4j_조회가_실패하면_GRAPH_NODE_QUERY_FAILED() {
		given(relatedArticleRepository.existsNode(any(), any()))
				.willThrow(new RuntimeException("bolt connection failed"));

		Throwable thrown = catchThrowable(() -> graphArticleService.getRelatedArticles(
				NodeType.EVENT, NODE_KEY, 2, null, null));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.GRAPH_NODE_QUERY_FAILED);
	}

	@Test
	void 비로그인이면_북마크를_조회하지_않고_모두_false다() {
		LocalDateTime t = LocalDateTime.of(2024, 1, 11, 9, 0);
		given(relatedArticleRepository.existsNode(any(), any())).willReturn(true);
		given(relatedArticleRepository.countRelatedArticles(any(), any())).willReturn(1L);
		given(relatedArticleRepository.findRefs(any(), any(), any(), anyInt()))
				.willReturn(List.of(ref(101L, t)));
		given(articleRepository.findAllWithOrganizationByArticleIdIn(List.of(101L)))
				.willReturn(List.of(article(101L, "a", "o", t)));

		RelatedArticlesResponse response = graphArticleService.getRelatedArticles(
				NodeType.EVENT, NODE_KEY, 2, null, null);

		assertThat(response.articles().get(0).bookmarked()).isFalse();
		verifyNoInteractions(userArticleFavoriteRepository);
	}

	@Test
	void Neo4j엔_있으나_MySQL에_없는_기사는_건너뛴다() {
		LocalDateTime t1 = LocalDateTime.of(2024, 1, 12, 9, 0);
		LocalDateTime t2 = LocalDateTime.of(2024, 1, 11, 9, 0);
		given(relatedArticleRepository.existsNode(any(), any())).willReturn(true);
		given(relatedArticleRepository.countRelatedArticles(any(), any())).willReturn(2L);
		given(relatedArticleRepository.findRefs(any(), any(), any(), anyInt()))
				.willReturn(List.of(ref(101L, t1), ref(102L, t2)));
		given(articleRepository.findAllWithOrganizationByArticleIdIn(List.of(101L, 102L)))
				.willReturn(List.of(article(101L, "a", "o", t1))); // 102 는 MySQL 에 없음

		RelatedArticlesResponse response = graphArticleService.getRelatedArticles(
				NodeType.EVENT, NODE_KEY, 2, null, null);

		assertThat(response.articles()).extracting(RelatedArticlesResponse.Item::articleId)
				.containsExactly(101L);
		assertThat(response.returnedCount()).isEqualTo(1);
		assertThat(response.totalCount()).isEqualTo(2L);
	}
}

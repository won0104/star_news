package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.graph.support.ArticleRelation;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.domain.user.dto.PersonalNodeArticlesResponse;
import com.starlightnews.backend.domain.user.exception.PersonalGraphErrorCode;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository.ReadArticleRow;
import com.starlightnews.backend.domain.user.repository.PersonalNodeArticleRepository;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.domain.user.support.ArticleReadCursor;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
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
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class PersonalNodeArticleServiceTest {

	@Mock
	private UserKnowledgeNodeRepository userKnowledgeNodeRepository;

	@Mock
	private PersonalNodeArticleRepository personalNodeArticleRepository;

	@Mock
	private ArticleReadRepository articleReadRepository;

	@Mock
	private UserArticleFavoriteRepository userArticleFavoriteRepository;

	@InjectMocks
	private PersonalNodeArticleService personalNodeArticleService;

	private static final long USER_ID = 1L;
	private static final String NODE_KEY = "00000024-0920-4000-8000-000000000001";
	private static final UserKnowledgeNodeId NODE_ID = new UserKnowledgeNodeId(USER_ID, NodeType.ENTITY, NODE_KEY);

	private UserKnowledgeNode node(String label) {
		return UserKnowledgeNode.forFirstClick(NODE_ID, label, "ECONOMY", LocalDateTime.of(2024, 5, 25, 5, 20));
	}

	private ReadArticleRow row(long articleId, String title, String org, String topicCode,
			LocalDateTime lastReadAt, String summary) {
		return new ReadArticleRow() {
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
	void 정상_조회는_읽은_기사를_최신순으로_북마크와_함께_반환한다() {
		LocalDateTime older = LocalDateTime.of(2026, 8, 30, 9, 0);
		LocalDateTime newer = LocalDateTime.of(2026, 8, 31, 9, 10);
		given(userKnowledgeNodeRepository.findById(NODE_ID)).willReturn(Optional.of(node("한국은행")));
		given(personalNodeArticleRepository.findRelatedArticleIds(ArticleRelation.ENTITY, NODE_KEY))
				.willReturn(List.of(101L, 102L));
		given(articleReadRepository.findFirstReadPage(USER_ID, List.of(101L, 102L), PageRequest.of(0, 3)))
				.willReturn(List.of(
						row(102L, "환율 급등", "연합뉴스", "ECONOMY", newer, null),
						row(101L, "기준금리 동결", "연합뉴스", "ECONOMY", older, "한국은행이 금리를 동결했다.")));
		given(userArticleFavoriteRepository.findFavoritedArticleIds(USER_ID, List.of(102L, 101L)))
				.willReturn(List.of(102L));

		PersonalNodeArticlesResponse response = personalNodeArticleService.getReadArticles(
				USER_ID, NodeType.ENTITY, NODE_KEY, 2, null);

		assertThat(response.node().nodeType()).isEqualTo("ENTITY");
		assertThat(response.node().nodeKey()).isEqualTo(NODE_KEY);
		assertThat(response.node().title()).isEqualTo("한국은행");

		assertThat(response.items()).extracting(PersonalNodeArticlesResponse.Item::articleId)
				.containsExactly(102L, 101L);
		assertThat(response.items().get(0).lastReadAt()).isEqualTo(newer.atOffset(ZoneOffset.ofHours(9)));
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
		given(userKnowledgeNodeRepository.findById(NODE_ID)).willReturn(Optional.of(node("한국은행")));
		given(personalNodeArticleRepository.findRelatedArticleIds(any(), any())).willReturn(List.of(1L, 2L, 3L));
		given(articleReadRepository.findFirstReadPage(eq(USER_ID), any(), eq(PageRequest.of(0, 3))))
				.willReturn(List.of(
						row(1L, "a", "org", "ECONOMY", t1, null),
						row(2L, "b", "org", "ECONOMY", t2, null),
						row(3L, "c", "org", "ECONOMY", t3, null)));
		given(userArticleFavoriteRepository.findFavoritedArticleIds(any(), any())).willReturn(List.of());

		PersonalNodeArticlesResponse response = personalNodeArticleService.getReadArticles(
				USER_ID, NodeType.ENTITY, NODE_KEY, 2, null);

		assertThat(response.items()).hasSize(2);
		assertThat(response.hasNext()).isTrue();
		ArticleReadCursor decoded = ArticleReadCursor.decode(response.nextCursor());
		assertThat(decoded.articleId()).isEqualTo(2L);
		assertThat(decoded.lastReadAt()).isEqualTo(t2.atOffset(ZoneOffset.ofHours(9)));
	}

	@Test
	void 커서가_있으면_findNextReadPage를_호출한다() {
		OffsetDateTime cursorTime = OffsetDateTime.of(2026, 8, 30, 9, 0, 0, 0, ZoneOffset.ofHours(9));
		String rawCursor = new ArticleReadCursor(cursorTime, 102L).encode();
		given(userKnowledgeNodeRepository.findById(NODE_ID)).willReturn(Optional.of(node("한국은행")));
		given(personalNodeArticleRepository.findRelatedArticleIds(any(), any())).willReturn(List.of(101L));
		given(articleReadRepository.findNextReadPage(any(), any(), any(), any(), any())).willReturn(List.of());

		personalNodeArticleService.getReadArticles(USER_ID, NodeType.ENTITY, NODE_KEY, 20, rawCursor);

		verify(articleReadRepository).findNextReadPage(
				eq(USER_ID), eq(List.of(101L)), eq(cursorTime.toLocalDateTime()), eq(102L), eq(PageRequest.of(0, 21)));
	}

	@Test
	void 잘못된_커서면_INVALID_CURSOR이고_아무것도_조회하지_않는다() {
		Throwable thrown = catchThrowable(() -> personalNodeArticleService.getReadArticles(
				USER_ID, NodeType.ENTITY, NODE_KEY, 20, "!!!not-base64!!!"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
		verifyNoInteractions(userKnowledgeNodeRepository, personalNodeArticleRepository,
				articleReadRepository, userArticleFavoriteRepository);
	}

	@Test
	void 개인_그래프에_없는_노드면_NODE_NOT_ACQUIRED이고_Neo4j를_조회하지_않는다() {
		given(userKnowledgeNodeRepository.findById(NODE_ID)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> personalNodeArticleService.getReadArticles(
				USER_ID, NodeType.ENTITY, NODE_KEY, 20, null));

		assertThat(errorCodeOf(thrown)).isEqualTo(PersonalGraphErrorCode.NODE_NOT_ACQUIRED);
		verifyNoInteractions(personalNodeArticleRepository, articleReadRepository, userArticleFavoriteRepository);
	}

	@Test
	void Neo4j_후보가_없으면_빈_목록이고_MySQL을_조회하지_않는다() {
		given(userKnowledgeNodeRepository.findById(NODE_ID)).willReturn(Optional.of(node("한국은행")));
		given(personalNodeArticleRepository.findRelatedArticleIds(any(), any())).willReturn(List.of());

		PersonalNodeArticlesResponse response = personalNodeArticleService.getReadArticles(
				USER_ID, NodeType.ENTITY, NODE_KEY, 20, null);

		assertThat(response.items()).isEmpty();
		assertThat(response.hasNext()).isFalse();
		verifyNoInteractions(articleReadRepository, userArticleFavoriteRepository);
	}

	@Test
	void 읽은_기사가_없으면_북마크를_조회하지_않는다() {
		given(userKnowledgeNodeRepository.findById(NODE_ID)).willReturn(Optional.of(node("한국은행")));
		given(personalNodeArticleRepository.findRelatedArticleIds(any(), any())).willReturn(List.of(101L));
		given(articleReadRepository.findFirstReadPage(any(), any(), any())).willReturn(List.of());

		PersonalNodeArticlesResponse response = personalNodeArticleService.getReadArticles(
				USER_ID, NodeType.ENTITY, NODE_KEY, 20, null);

		assertThat(response.items()).isEmpty();
		verify(userArticleFavoriteRepository, never()).findFavoritedArticleIds(any(), any());
	}

	@Test
	void Neo4j_조회가_실패하면_INTERNAL_SERVER_ERROR() {
		given(userKnowledgeNodeRepository.findById(NODE_ID)).willReturn(Optional.of(node("한국은행")));
		given(personalNodeArticleRepository.findRelatedArticleIds(any(), any()))
				.willThrow(new RuntimeException("bolt connection failed"));

		Throwable thrown = catchThrowable(() -> personalNodeArticleService.getReadArticles(
				USER_ID, NodeType.ENTITY, NODE_KEY, 20, null));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.INTERNAL_SERVER_ERROR);
	}

	@Test
	void 요약이_120자_넘으면_120자로_자르고_말줄임표를_붙인다() {
		String longSummary = "가".repeat(150);
		given(userKnowledgeNodeRepository.findById(NODE_ID)).willReturn(Optional.of(node("한국은행")));
		given(personalNodeArticleRepository.findRelatedArticleIds(any(), any())).willReturn(List.of(101L));
		given(articleReadRepository.findFirstReadPage(any(), any(), any())).willReturn(List.of(
				row(101L, "제목", "연합뉴스", "ECONOMY", LocalDateTime.of(2026, 8, 31, 9, 0), longSummary)));
		given(userArticleFavoriteRepository.findFavoritedArticleIds(any(), any())).willReturn(List.of());

		PersonalNodeArticlesResponse response = personalNodeArticleService.getReadArticles(
				USER_ID, NodeType.ENTITY, NODE_KEY, 20, null);

		String preview = response.items().get(0).summaryPreview();
		assertThat(preview).hasSize(121).endsWith("…").isEqualTo("가".repeat(120) + "…");
	}
}

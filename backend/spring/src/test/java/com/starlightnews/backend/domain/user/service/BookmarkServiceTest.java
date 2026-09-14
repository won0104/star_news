package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.StreamSupport;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.domain.UserArticleFavoriteId;
import com.starlightnews.backend.domain.user.dto.ArticleBookmarkItem;
import com.starlightnews.backend.domain.user.dto.NodeBookmarkItem;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksRequest;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksRequest.ArticleBookmarkChange;
import com.starlightnews.backend.domain.user.dto.UpdateArticleBookmarksResponse;
import com.starlightnews.backend.domain.user.exception.UserErrorCode;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository.ArticleBookmarkRow;
import com.starlightnews.backend.domain.user.repository.NodeName;
import com.starlightnews.backend.domain.user.repository.NodeSnapshotRepository;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.domain.user.repository.UserNodeFavoriteRepository;
import com.starlightnews.backend.domain.user.repository.UserNodeFavoriteRepository.NodeFavoriteRow;
import com.starlightnews.backend.domain.user.support.ArticleBookmarkCursor;
import com.starlightnews.backend.domain.user.support.NodeBookmarkCursor;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.response.CursorResponse;
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
	private ArticleRepository articleRepository;

	@Mock
	private UserArticleFavoriteRepository userArticleFavoriteRepository;

	@Mock
	private UserNodeFavoriteRepository userNodeFavoriteRepository;

	@Mock
	private NodeSnapshotRepository nodeSnapshotRepository;

	@InjectMocks
	private BookmarkService bookmarkService;

	@BeforeEach
	void setUpActiveUser() {
		org.mockito.Mockito.lenient().when(userRepository.findById(USER_ID))
				.thenReturn(Optional.of(User.create("login", "hash", "nickname")));
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

	@Test
	void 등록과_해제를_한_요청에서_최종_상태로_반영하고_요청순서대로_응답한다() {
		UpdateArticleBookmarksRequest request = request(
				new ArticleBookmarkChange(101L, true),
				new ArticleBookmarkChange(102L, false),
				new ArticleBookmarkChange(103L, true),
				new ArticleBookmarkChange(104L, false));
		given(articleRepository.findArticleIdsByIdInAndAnalysisStatus(
				eq(Set.of(101L, 103L)), eq(AnalysisStatus.COMPLETED)))
				.willReturn(List.of(101L, 103L));
		given(userArticleFavoriteRepository.findFavoritedArticleIds(
				eq(USER_ID), eq(Set.of(101L, 102L, 103L, 104L))))
				.willReturn(List.of(101L, 102L));

		UpdateArticleBookmarksResponse response =
				bookmarkService.updateArticleBookmarks(USER_ID, request);

		assertThat(response.results())
				.extracting(result -> result.articleId() + ":" + result.bookmarked())
				.containsExactly("101:true", "102:false", "103:true", "104:false");
		verify(userArticleFavoriteRepository).saveAll(org.mockito.ArgumentMatchers.argThat(favorites -> {
			List<UserArticleFavoriteId> savedIds = StreamSupport.stream(favorites.spliterator(), false)
					.map(favorite -> favorite.getId())
					.toList();
			return savedIds.equals(List.of(new UserArticleFavoriteId(USER_ID, 103L)));
		}));
		verify(userArticleFavoriteRepository).deleteByUserIdAndArticleIds(USER_ID, List.of(102L));
	}

	@Test
	void 빈_changes는_EMPTY_CHANGES이고_DB를_조회하지_않는다() {
		assertThatThrownBy(() -> bookmarkService.updateArticleBookmarks(
				USER_ID, new UpdateArticleBookmarksRequest(List.of())))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.EMPTY_CHANGES));

		verifyNoInteractions(articleRepository, userArticleFavoriteRepository);
	}

	@Test
	void 같은_articleId가_중복이면_DUPLICATED_ARTICLE_CHANGE이다() {
		UpdateArticleBookmarksRequest request = request(
				new ArticleBookmarkChange(101L, true),
				new ArticleBookmarkChange(101L, false));

		assertThatThrownBy(() -> bookmarkService.updateArticleBookmarks(USER_ID, request))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(UserErrorCode.DUPLICATED_ARTICLE_CHANGE));

		verifyNoInteractions(articleRepository, userArticleFavoriteRepository);
	}

	@Test
	void 등록할_기사_중_COMPLETED가_아닌_기사가_있으면_ARTICLE_NOT_FOUND이다() {
		UpdateArticleBookmarksRequest request = request(
				new ArticleBookmarkChange(101L, true),
				new ArticleBookmarkChange(102L, true));
		given(articleRepository.findArticleIdsByIdInAndAnalysisStatus(
				eq(Set.of(101L, 102L)), eq(AnalysisStatus.COMPLETED)))
				.willReturn(List.of(101L));

		assertThatThrownBy(() -> bookmarkService.updateArticleBookmarks(USER_ID, request))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode()).isEqualTo(UserErrorCode.ARTICLE_NOT_FOUND));

		verifyNoInteractions(userArticleFavoriteRepository);
	}

	@Test
	void 해제만_요청하면_기사_공개상태를_조회하지_않고_없는_북마크도_성공한다() {
		UpdateArticleBookmarksRequest request = request(new ArticleBookmarkChange(999L, false));
		given(userArticleFavoriteRepository.findFavoritedArticleIds(USER_ID, Set.of(999L)))
				.willReturn(List.of());

		UpdateArticleBookmarksResponse response =
				bookmarkService.updateArticleBookmarks(USER_ID, request);

		assertThat(response.results()).singleElement().satisfies(result -> {
			assertThat(result.articleId()).isEqualTo(999L);
			assertThat(result.bookmarked()).isFalse();
		});
		verifyNoInteractions(articleRepository);
		verify(userArticleFavoriteRepository, never()).saveAll(any());
		verify(userArticleFavoriteRepository, never()).deleteByUserIdAndArticleIds(any(), any());
	}

	@Test
	void Node첫페이지는_size보다_한개더_조회하고_Neo4j이름을_MySQL순서대로_조합한다() {
		String entityId = "00000000-0000-0000-0000-000000000001";
		String eventId = "00000000-0000-0000-0000-000000000002";
		String storyId = "00000000-0000-0000-0000-000000000003";
		LocalDateTime newest = LocalDateTime.of(2026, 9, 14, 9, 0);
		LocalDateTime older = LocalDateTime.of(2026, 9, 13, 9, 0);
		given(userNodeFavoriteRepository.findFirstNodeFavoritePage(
				eq(USER_ID),
				eq(List.of("ENTITY", "EVENT", "STATEMENT", "STORY")),
				eq(PageRequest.of(0, 3))))
				.willReturn(List.of(
						nodeRow("ENTITY", entityId, newest),
						nodeRow("EVENT", eventId, older),
						nodeRow("STORY", storyId, older.minusDays(1))));
		given(nodeSnapshotRepository.findNames(NodeType.ENTITY, List.of(entityId)))
				.willReturn(List.of(new NodeName(entityId, "한국은행")));
		given(nodeSnapshotRepository.findNames(NodeType.EVENT, List.of(eventId)))
				.willReturn(List.of(new NodeName(eventId, "기준금리 동결")));

		CursorResponse<NodeBookmarkItem> response =
				bookmarkService.getNodeBookmarks(USER_ID, null, null, 2);

		assertThat(response.items()).extracting(NodeBookmarkItem::nodeId)
				.containsExactly(entityId, eventId);
		assertThat(response.items()).extracting(NodeBookmarkItem::name)
				.containsExactly("한국은행", "기준금리 동결");
		assertThat(response.items().get(0).nodeType()).isEqualTo(NodeType.ENTITY);
		assertThat(response.items().get(0).bookmarkedAt()).isEqualTo(newest.atOffset(KST));
		assertThat(response.hasNext()).isTrue();
		assertThat(NodeBookmarkCursor.decode(response.nextCursor()))
				.isEqualTo(new NodeBookmarkCursor(older.atOffset(KST), NodeType.EVENT, eventId));
		verify(nodeSnapshotRepository, never()).findNames(eq(NodeType.STORY), any());
	}

	@Test
	void Node다음페이지는_필터와_커서시각을_KST_DB값으로_변환해_조회한다() {
		String nodeId = "00000000-0000-0000-0000-000000000001";
		OffsetDateTime utcTime = OffsetDateTime.of(2026, 9, 14, 0, 0, 0, 0, ZoneOffset.UTC);
		String cursor = new NodeBookmarkCursor(utcTime, NodeType.ENTITY, nodeId).encode();
		given(userNodeFavoriteRepository.findNextNodeFavoritePage(any(), any(), any(), any(), any(), any()))
				.willReturn(List.of());

		CursorResponse<NodeBookmarkItem> response =
				bookmarkService.getNodeBookmarks(USER_ID, "entity", cursor, 20);

		verify(userNodeFavoriteRepository).findNextNodeFavoritePage(
				eq(USER_ID),
				eq(List.of("ENTITY")),
				eq(LocalDateTime.of(2026, 9, 14, 9, 0)),
				eq("ENTITY"),
				eq(nodeId),
				eq(PageRequest.of(0, 21)));
		assertThat(response.items()).isEmpty();
		assertThat(response.hasNext()).isFalse();
		verifyNoInteractions(nodeSnapshotRepository);
	}

	@Test
	void 즐겨찾기대상이_아닌_NodeType은_INVALID_NODE_TYPE이다() {
		assertThatThrownBy(() -> bookmarkService.getNodeBookmarks(USER_ID, "CONCEPT", null, 20))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(GraphErrorCode.INVALID_NODE_TYPE));
		assertThatThrownBy(() -> bookmarkService.getNodeBookmarks(USER_ID, "ARTICLE", null, 20))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(GraphErrorCode.INVALID_NODE_TYPE));
		verifyNoInteractions(userNodeFavoriteRepository, nodeSnapshotRepository);
	}

	@Test
	void MySQL참조에_대응하는_Neo4j_Node가_없으면_GRAPH_NODE_QUERY_FAILED이다() {
		String nodeId = "00000000-0000-0000-0000-000000000001";
		given(userNodeFavoriteRepository.findFirstNodeFavoritePage(any(), any(), any()))
				.willReturn(List.of(nodeRow(
						"ENTITY", nodeId, LocalDateTime.of(2026, 9, 14, 9, 0))));
		given(nodeSnapshotRepository.findNames(NodeType.ENTITY, List.of(nodeId)))
				.willReturn(List.of());

		assertThatThrownBy(() -> bookmarkService.getNodeBookmarks(USER_ID, null, null, 20))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(GraphErrorCode.GRAPH_NODE_QUERY_FAILED));
	}

	@Test
	void Neo4j이름조회가_실패하면_GRAPH_NODE_QUERY_FAILED이다() {
		String nodeId = "00000000-0000-0000-0000-000000000001";
		given(userNodeFavoriteRepository.findFirstNodeFavoritePage(any(), any(), any()))
				.willReturn(List.of(nodeRow(
						"ENTITY", nodeId, LocalDateTime.of(2026, 9, 14, 9, 0))));
		given(nodeSnapshotRepository.findNames(NodeType.ENTITY, List.of(nodeId)))
				.willThrow(new RuntimeException("bolt connection failed"));

		assertThatThrownBy(() -> bookmarkService.getNodeBookmarks(USER_ID, null, null, 20))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(GraphErrorCode.GRAPH_NODE_QUERY_FAILED));
	}

	private UpdateArticleBookmarksRequest request(ArticleBookmarkChange... changes) {
		return new UpdateArticleBookmarksRequest(List.of(changes));
	}

	private NodeFavoriteRow nodeRow(String nodeType, String nodeId, LocalDateTime bookmarkedAt) {
		return new NodeFavoriteRow() {
			@Override
			public String getNodeType() {
				return nodeType;
			}

			@Override
			public String getNodeId() {
				return nodeId;
			}

			@Override
			public LocalDateTime getBookmarkedAt() {
				return bookmarkedAt;
			}
		};
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

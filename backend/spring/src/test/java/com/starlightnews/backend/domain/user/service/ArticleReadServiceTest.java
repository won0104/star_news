package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.user.domain.ArticleRead;
import com.starlightnews.backend.domain.user.domain.ArticleReadId;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.domain.user.repository.ArticleNodeSnapshot;
import com.starlightnews.backend.domain.user.repository.ArticleNodeSnapshotRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import com.starlightnews.backend.global.error.ErrorCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class ArticleReadServiceTest {

	@Mock
	private ArticleReadRepository articleReadRepository;

	@Mock
	private ArticleRepository articleRepository;

	@Mock
	private ArticleNodeSnapshotRepository articleNodeSnapshotRepository;

	@Mock
	private UserKnowledgeNodeRepository userKnowledgeNodeRepository;

	@InjectMocks
	private ArticleReadService articleReadService;

	private static final long USER_ID = 1L;
	private static final long ARTICLE_ID = 101L;
	private static final String ARTICLE_NODE_KEY = "00000010-0920-4000-8000-000000000001";
	private static final String EVENT_KEY = "00000020-0920-4000-8000-000000000001";
	private static final String ENTITY_KEY = "00000020-0920-4000-8000-000000000002";

	private ErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return ((BusinessException) throwable).getErrorCode();
	}

	/** 분석된 기사면 nodeId 가 있고, 분석 전이면 null 이다. */
	private void givenArticle(String nodeId) {
		given(articleRepository.findGraphRefByArticleId(ARTICLE_ID)).willReturn(Optional.of(
				new ArticleRepository.ArticleGraphRef() {
					@Override
					public Long getArticleId() {
						return ARTICLE_ID;
					}

					@Override
					public String getNodeId() {
						return nodeId;
					}
				}));
	}

	private UserKnowledgeNodeId nodeId(NodeType nodeType, String nodeKey) {
		return new UserKnowledgeNodeId(USER_ID, nodeType, nodeKey);
	}

	@Test
	void 기존_Row가_있으면_incrementRead만_한다() {
		givenArticle(null);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(1);

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verify(articleReadRepository).incrementRead(
				eq(new ArticleReadId(USER_ID, ARTICLE_ID)), any(LocalDateTime.class));
		verify(articleReadRepository, never()).save(any());
	}

	@Test
	void Row가_없으면_click_count_1인_새_Row를_만든다() {
		givenArticle(null);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(0);

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		ArgumentCaptor<ArticleRead> captor = ArgumentCaptor.forClass(ArticleRead.class);
		verify(articleReadRepository).save(captor.capture());
		ArticleRead saved = captor.getValue();
		assertThat(saved.getId()).isEqualTo(new ArticleReadId(USER_ID, ARTICLE_ID));
		assertThat(saved.getClickCount()).isEqualTo(1);
		assertThat(saved.getFirstReadAt()).isEqualTo(saved.getLastReadAt());
	}

	@Test
	void 없는_기사면_RESOURCE_NOT_FOUND이고_저장하지_않는다() {
		given(articleRepository.findGraphRefByArticleId(ARTICLE_ID)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> articleReadService.recordRead(USER_ID, ARTICLE_ID));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.RESOURCE_NOT_FOUND);
		verifyNoInteractions(articleReadRepository, articleNodeSnapshotRepository, userKnowledgeNodeRepository);
	}

	@Test
	void 첫_열람_동시_요청으로_save가_충돌하면_incrementRead로_되돌린다() {
		givenArticle(null);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(0, 1);
		given(articleReadRepository.save(any()))
				.willThrow(new DataIntegrityViolationException("duplicate key"));

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verify(articleReadRepository, times(2)).incrementRead(any(), any());
	}

	@Test
	void 분석_전_기사면_열람만_남기고_Neo4j를_보지_않는다() {
		givenArticle(null);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(1);

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verifyNoInteractions(articleNodeSnapshotRepository, userKnowledgeNodeRepository);
	}

	@Test
	void 최초_열람이면_기존_Node의_고유_기사_수를_늘린다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(0);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.EVENT, EVENT_KEY, "기준금리 동결", "ECONOMY")));
		given(userKnowledgeNodeRepository.findExistingIds(any()))
				.willReturn(List.of(nodeId(NodeType.EVENT, EVENT_KEY)));

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verify(userKnowledgeNodeRepository).incrementReadForAll(any(), any(LocalDateTime.class));
		verify(userKnowledgeNodeRepository, never()).touchLastSeenForAll(any(), any());
		verify(userKnowledgeNodeRepository, never()).save(any());
	}

	@Test
	void 재열람이면_고유_기사_수는_그대로_두고_lastSeenAt만_갱신한다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(1);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.EVENT, EVENT_KEY, "기준금리 동결", "ECONOMY")));
		given(userKnowledgeNodeRepository.findExistingIds(any()))
				.willReturn(List.of(nodeId(NodeType.EVENT, EVENT_KEY)));

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verify(userKnowledgeNodeRepository).touchLastSeenForAll(any(), any(LocalDateTime.class));
		verify(userKnowledgeNodeRepository, never()).incrementReadForAll(any(), any());
	}

	@Test
	void 없던_Node는_read_article_count_1로_새로_만든다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(0);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.ENTITY, ENTITY_KEY, "한국은행", null)));
		given(userKnowledgeNodeRepository.findExistingIds(any())).willReturn(List.of());

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		ArgumentCaptor<UserKnowledgeNode> captor = ArgumentCaptor.forClass(UserKnowledgeNode.class);
		verify(userKnowledgeNodeRepository).save(captor.capture());
		UserKnowledgeNode saved = captor.getValue();
		assertThat(saved.getId()).isEqualTo(nodeId(NodeType.ENTITY, ENTITY_KEY));
		assertThat(saved.getNodeLabel()).isEqualTo("한국은행");
		assertThat(saved.getTopicCode()).isNull(); // ENTITY 는 CLASSIFIED_AS 가 없어 topic 이 비어 있다
		assertThat(saved.getReadArticleCount()).isEqualTo(1);
		assertThat(saved.getNodeClickCount()).isZero();
		assertThat(saved.getFirstSeenAt()).isEqualTo(saved.getLastSeenAt());
		verify(userKnowledgeNodeRepository, never()).incrementReadForAll(any(), any());
	}

	@Test
	void 기존_Node와_새_Node가_섞이면_갱신과_생성을_나눠서_처리한다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(0);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.EVENT, EVENT_KEY, "기준금리 동결", "ECONOMY"),
				new ArticleNodeSnapshot(NodeType.ENTITY, ENTITY_KEY, "한국은행", null)));
		given(userKnowledgeNodeRepository.findExistingIds(any()))
				.willReturn(List.of(nodeId(NodeType.EVENT, EVENT_KEY)));

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		ArgumentCaptor<Collection<UserKnowledgeNodeId>> idsCaptor = ArgumentCaptor.forClass(Collection.class);
		verify(userKnowledgeNodeRepository).incrementReadForAll(idsCaptor.capture(), any(LocalDateTime.class));
		assertThat(idsCaptor.getValue()).containsExactly(nodeId(NodeType.EVENT, EVENT_KEY));

		ArgumentCaptor<UserKnowledgeNode> savedCaptor = ArgumentCaptor.forClass(UserKnowledgeNode.class);
		verify(userKnowledgeNodeRepository).save(savedCaptor.capture());
		assertThat(savedCaptor.getValue().getId()).isEqualTo(nodeId(NodeType.ENTITY, ENTITY_KEY));
	}

	@Test
	void 같은_Node가_중복으로_오면_한_번만_처리한다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(0);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.EVENT, EVENT_KEY, "기준금리 동결", "ECONOMY"),
				new ArticleNodeSnapshot(NodeType.EVENT, EVENT_KEY, "기준금리 동결", "ECONOMY")));
		given(userKnowledgeNodeRepository.findExistingIds(any())).willReturn(List.of());

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verify(userKnowledgeNodeRepository, times(1)).save(any());
	}

	@Test
	void 연결_Node가_없으면_user_knowledge_nodes를_건드리지_않는다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(1);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of());

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verifyNoInteractions(userKnowledgeNodeRepository);
	}

	@Test
	void 다른_기사가_같은_Node를_먼저_만들어_save가_충돌하면_갱신으로_되돌린다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(0);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.ENTITY, ENTITY_KEY, "한국은행", null)));
		given(userKnowledgeNodeRepository.findExistingIds(any())).willReturn(List.of());
		given(userKnowledgeNodeRepository.save(any()))
				.willThrow(new DataIntegrityViolationException("duplicate key"));

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		ArgumentCaptor<Collection<UserKnowledgeNodeId>> idsCaptor = ArgumentCaptor.forClass(Collection.class);
		verify(userKnowledgeNodeRepository).incrementReadForAll(idsCaptor.capture(), any(LocalDateTime.class));
		assertThat(idsCaptor.getValue()).containsExactly(nodeId(NodeType.ENTITY, ENTITY_KEY));
	}

	@Test
	void Neo4j_조회가_실패하면_INTERNAL_SERVER_ERROR() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.incrementRead(any(), any())).willReturn(1);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY))
				.willThrow(new RuntimeException("bolt connection failed"));

		Throwable thrown = catchThrowable(() -> articleReadService.recordRead(USER_ID, ARTICLE_ID));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.INTERNAL_SERVER_ERROR);
		verifyNoInteractions(userKnowledgeNodeRepository);
	}
}

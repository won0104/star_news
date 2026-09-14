package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
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
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class ArticleReadServiceTest {

	/** MySQL upsert 영향 행 수: 1=INSERT(최초 열람), 2=기존 행 갱신(재열람). */
	private static final int INSERTED = 1;
	private static final int UPDATED = 2;

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

	@Test
	void 최초_열람이면_article_reads를_upsert한다() {
		givenArticle(null);
		given(articleReadRepository.upsertRead(anyLong(), anyLong(), any())).willReturn(INSERTED);

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verify(articleReadRepository).upsertRead(eq(USER_ID), eq(ARTICLE_ID), any(LocalDateTime.class));
	}

	@Test
	void 없는_기사면_RESOURCE_NOT_FOUND이고_아무것도_저장하지_않는다() {
		given(articleRepository.findGraphRefByArticleId(ARTICLE_ID)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> articleReadService.recordRead(USER_ID, ARTICLE_ID));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.RESOURCE_NOT_FOUND);
		verifyNoInteractions(articleReadRepository, articleNodeSnapshotRepository, userKnowledgeNodeRepository);
	}

	@Test
	void 분석_전_기사면_열람만_남기고_Neo4j를_보지_않는다() {
		givenArticle(null);
		given(articleReadRepository.upsertRead(anyLong(), anyLong(), any())).willReturn(INSERTED);

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verifyNoInteractions(articleNodeSnapshotRepository, userKnowledgeNodeRepository);
	}

	@Test
	void 최초_열람이면_Node의_고유_기사_수를_1_늘리도록_upsert한다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.upsertRead(anyLong(), anyLong(), any())).willReturn(INSERTED);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.EVENT, EVENT_KEY, "기준금리 동결", "ECONOMY")));

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verify(userKnowledgeNodeRepository).upsertRead(eq(USER_ID), eq("EVENT"), eq(EVENT_KEY),
				eq("기준금리 동결"), eq("ECONOMY"), eq(1), any(LocalDateTime.class));
	}

	@Test
	void 재열람이면_고유_기사_수를_늘리지_않도록_upsert한다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.upsertRead(anyLong(), anyLong(), any())).willReturn(UPDATED);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.EVENT, EVENT_KEY, "기준금리 동결", "ECONOMY")));

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		// 이미 있는 Node 면 +0, 없던 Node 면 INSERT 쪽에서 1 로 시작한다. 둘 다 이 한 문장이 처리한다.
		verify(userKnowledgeNodeRepository).upsertRead(eq(USER_ID), eq("EVENT"), eq(EVENT_KEY),
				eq("기준금리 동결"), eq("ECONOMY"), eq(0), any(LocalDateTime.class));
	}

	@Test
	void topicCode가_없는_Node도_그대로_upsert한다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.upsertRead(anyLong(), anyLong(), any())).willReturn(INSERTED);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.ENTITY, ENTITY_KEY, "한국은행", null)));

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		// ENTITY 는 CLASSIFIED_AS 가 없어 topic 이 비어 있다
		verify(userKnowledgeNodeRepository).upsertRead(eq(USER_ID), eq("ENTITY"), eq(ENTITY_KEY),
				eq("한국은행"), isNull(), eq(1), any(LocalDateTime.class));
	}

	@Test
	void 연결_Node가_여러_개면_각각_upsert한다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.upsertRead(anyLong(), anyLong(), any())).willReturn(INSERTED);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.EVENT, EVENT_KEY, "기준금리 동결", "ECONOMY"),
				new ArticleNodeSnapshot(NodeType.ENTITY, ENTITY_KEY, "한국은행", null)));

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verify(userKnowledgeNodeRepository, times(2))
				.upsertRead(anyLong(), anyString(), anyString(), anyString(), any(), anyInt(), any());
	}

	@Test
	void 같은_Node가_중복으로_오면_한_번만_upsert한다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.upsertRead(anyLong(), anyLong(), any())).willReturn(INSERTED);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of(
				new ArticleNodeSnapshot(NodeType.EVENT, EVENT_KEY, "기준금리 동결", "ECONOMY"),
				new ArticleNodeSnapshot(NodeType.EVENT, EVENT_KEY, "기준금리 동결", "ECONOMY")));

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verify(userKnowledgeNodeRepository, times(1))
				.upsertRead(anyLong(), anyString(), anyString(), anyString(), any(), anyInt(), any());
	}

	@Test
	void 연결_Node가_없으면_user_knowledge_nodes를_건드리지_않는다() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.upsertRead(anyLong(), anyLong(), any())).willReturn(UPDATED);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY)).willReturn(List.of());

		articleReadService.recordRead(USER_ID, ARTICLE_ID);

		verifyNoInteractions(userKnowledgeNodeRepository);
	}

	@Test
	void Neo4j_조회가_실패하면_INTERNAL_SERVER_ERROR() {
		givenArticle(ARTICLE_NODE_KEY);
		given(articleReadRepository.upsertRead(anyLong(), anyLong(), any())).willReturn(UPDATED);
		given(articleNodeSnapshotRepository.findConnectedNodes(ARTICLE_NODE_KEY))
				.willThrow(new RuntimeException("bolt connection failed"));

		Throwable thrown = catchThrowable(() -> articleReadService.recordRead(USER_ID, ARTICLE_ID));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.INTERNAL_SERVER_ERROR);
		verify(userKnowledgeNodeRepository, never())
				.upsertRead(anyLong(), anyString(), anyString(), anyString(), any(), anyInt(), any());
	}
}

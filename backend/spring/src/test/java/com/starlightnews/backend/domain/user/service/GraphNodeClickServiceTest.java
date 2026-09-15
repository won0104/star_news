package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.util.Optional;

import com.starlightnews.backend.domain.user.cache.ExploredNodeCountCache;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.domain.user.repository.NodeSnapshot;
import com.starlightnews.backend.domain.user.repository.NodeSnapshotRepository;
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
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class GraphNodeClickServiceTest {

	@Mock
	private UserKnowledgeNodeRepository userKnowledgeNodeRepository;

	@Mock
	private NodeSnapshotRepository nodeSnapshotRepository;

	@Mock
	private ExploredNodeCountCache exploredNodeCountCache;

	@InjectMocks
	private GraphNodeClickService graphNodeClickService;

	private static final long USER_ID = 1L;
	private static final String NODE_KEY = "00000024-0920-4000-8000-000000000001";

	private ErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 기존_Row가_있으면_incrementClick만_하고_Neo4j를_보지_않는다() {
		given(userKnowledgeNodeRepository.existsById(any())).willReturn(true);

		graphNodeClickService.recordClick(USER_ID, NodeType.ENTITY, NODE_KEY);

		verify(userKnowledgeNodeRepository).incrementClick(
				eq(new UserKnowledgeNodeId(USER_ID, NodeType.ENTITY, NODE_KEY)), any(LocalDateTime.class));
		verify(userKnowledgeNodeRepository, never())
				.upsertClick(any(), any(), any(), any(), any(), any());
		verifyNoInteractions(nodeSnapshotRepository);
		verify(exploredNodeCountCache).evict(USER_ID);
	}

	@Test
	void Row가_없으면_Neo4j_스냅샷으로_새_Row를_만든다() {
		given(userKnowledgeNodeRepository.existsById(any())).willReturn(false);
		given(nodeSnapshotRepository.findSnapshot(NodeType.ENTITY, NODE_KEY))
				.willReturn(Optional.of(new NodeSnapshot("한국은행", "ECONOMY")));

		graphNodeClickService.recordClick(USER_ID, NodeType.ENTITY, NODE_KEY);

		verify(userKnowledgeNodeRepository).upsertClick(eq(USER_ID), eq("ENTITY"), eq(NODE_KEY),
				eq("한국은행"), eq("ECONOMY"), any(LocalDateTime.class));
		verify(userKnowledgeNodeRepository, never()).incrementClick(any(), any());
		verify(exploredNodeCountCache).evict(USER_ID);
	}

	@Test
	void Neo4j에도_Node가_없으면_RESOURCE_NOT_FOUND이고_저장하지_않는다() {
		given(userKnowledgeNodeRepository.existsById(any())).willReturn(false);
		given(nodeSnapshotRepository.findSnapshot(NodeType.ENTITY, NODE_KEY)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(
				() -> graphNodeClickService.recordClick(USER_ID, NodeType.ENTITY, NODE_KEY));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.RESOURCE_NOT_FOUND);
		verify(userKnowledgeNodeRepository, never())
				.upsertClick(any(), any(), any(), any(), any(), any());
		verifyNoInteractions(exploredNodeCountCache); // 실패했으니 캐시를 건드릴 이유가 없다
	}

	@Test
	void Neo4j_조회가_실패하면_INTERNAL_SERVER_ERROR() {
		given(userKnowledgeNodeRepository.existsById(any())).willReturn(false);
		given(nodeSnapshotRepository.findSnapshot(NodeType.ENTITY, NODE_KEY))
				.willThrow(new RuntimeException("bolt connection failed"));

		Throwable thrown = catchThrowable(
				() -> graphNodeClickService.recordClick(USER_ID, NodeType.ENTITY, NODE_KEY));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.INTERNAL_SERVER_ERROR);
		verifyNoInteractions(exploredNodeCountCache); // 실패했으니 캐시를 건드릴 이유가 없다
	}
}

package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.util.Optional;

import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
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
class GraphNodeClickServiceTest {

	@Mock
	private UserKnowledgeNodeRepository userKnowledgeNodeRepository;

	@Mock
	private NodeSnapshotRepository nodeSnapshotRepository;

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
		given(userKnowledgeNodeRepository.incrementClick(any(), any())).willReturn(1);

		graphNodeClickService.recordClick(USER_ID, NodeType.ENTITY, NODE_KEY);

		verify(userKnowledgeNodeRepository).incrementClick(
				eq(new UserKnowledgeNodeId(USER_ID, NodeType.ENTITY, NODE_KEY)), any(LocalDateTime.class));
		verify(userKnowledgeNodeRepository, never()).save(any());
		verifyNoInteractions(nodeSnapshotRepository);
	}

	@Test
	void Row가_없으면_Neo4j_스냅샷으로_새_Row를_만든다() {
		given(userKnowledgeNodeRepository.incrementClick(any(), any())).willReturn(0);
		given(nodeSnapshotRepository.findSnapshot(NodeType.ENTITY, NODE_KEY))
				.willReturn(Optional.of(new NodeSnapshot("한국은행", "ECONOMY")));

		graphNodeClickService.recordClick(USER_ID, NodeType.ENTITY, NODE_KEY);

		ArgumentCaptor<UserKnowledgeNode> captor = ArgumentCaptor.forClass(UserKnowledgeNode.class);
		verify(userKnowledgeNodeRepository).save(captor.capture());
		UserKnowledgeNode saved = captor.getValue();
		assertThat(saved.getId()).isEqualTo(new UserKnowledgeNodeId(USER_ID, NodeType.ENTITY, NODE_KEY));
		assertThat(saved.getNodeLabel()).isEqualTo("한국은행");
		assertThat(saved.getTopicCode()).isEqualTo("ECONOMY");
		assertThat(saved.getNodeClickCount()).isEqualTo(1);
		assertThat(saved.getReadArticleCount()).isZero();
		assertThat(saved.getFirstSeenAt()).isEqualTo(saved.getLastSeenAt());
	}

	@Test
	void Neo4j에도_Node가_없으면_RESOURCE_NOT_FOUND이고_저장하지_않는다() {
		given(userKnowledgeNodeRepository.incrementClick(any(), any())).willReturn(0);
		given(nodeSnapshotRepository.findSnapshot(NodeType.ENTITY, NODE_KEY)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(
				() -> graphNodeClickService.recordClick(USER_ID, NodeType.ENTITY, NODE_KEY));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.RESOURCE_NOT_FOUND);
		verify(userKnowledgeNodeRepository, never()).save(any());
	}

	@Test
	void Neo4j_조회가_실패하면_INTERNAL_SERVER_ERROR() {
		given(userKnowledgeNodeRepository.incrementClick(any(), any())).willReturn(0);
		given(nodeSnapshotRepository.findSnapshot(NodeType.ENTITY, NODE_KEY))
				.willThrow(new RuntimeException("bolt connection failed"));

		Throwable thrown = catchThrowable(
				() -> graphNodeClickService.recordClick(USER_ID, NodeType.ENTITY, NODE_KEY));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.INTERNAL_SERVER_ERROR);
	}

	@Test
	void 첫_클릭_동시_요청으로_save가_충돌하면_incrementClick으로_되돌린다() {
		given(userKnowledgeNodeRepository.incrementClick(any(), any())).willReturn(0, 1);
		given(nodeSnapshotRepository.findSnapshot(NodeType.ENTITY, NODE_KEY))
				.willReturn(Optional.of(new NodeSnapshot("한국은행", "ECONOMY")));
		given(userKnowledgeNodeRepository.save(any()))
				.willThrow(new DataIntegrityViolationException("duplicate key"));

		graphNodeClickService.recordClick(USER_ID, NodeType.ENTITY, NODE_KEY);

		verify(userKnowledgeNodeRepository, times(2)).incrementClick(any(), any());
	}
}

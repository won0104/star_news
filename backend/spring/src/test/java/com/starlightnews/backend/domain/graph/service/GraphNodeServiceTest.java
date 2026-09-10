package com.starlightnews.backend.domain.graph.service;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Optional;

import com.starlightnews.backend.domain.graph.dto.GraphNodeDetailResponse;
import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.graph.repository.GraphNodeRecord;
import com.starlightnews.backend.domain.graph.repository.GraphNodeRepository;
import com.starlightnews.backend.domain.user.domain.UserNodeFavoriteId;
import com.starlightnews.backend.domain.user.repository.UserNodeFavoriteRepository;
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
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class GraphNodeServiceTest {

	@Mock
	private GraphNodeRepository graphNodeRepository;

	@Mock
	private UserNodeFavoriteRepository userNodeFavoriteRepository;

	@InjectMocks
	private GraphNodeService graphNodeService;

	private static final String NODE_KEY = "00000020-0920-4000-8000-000000000001";
	private static final OffsetDateTime TIME = OffsetDateTime.of(2024, 1, 11, 9, 0, 0, 0, ZoneOffset.ofHours(9));

	private ErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 로그인_사용자가_즐겨찾기한_노드는_bookmarked_true로_조립된다() {
		given(graphNodeRepository.findNode(NodeType.EVENT, NODE_KEY))
				.willReturn(Optional.of(new GraphNodeRecord("한국은행 기준금리 동결", null, TIME)));
		given(userNodeFavoriteRepository.existsById(new UserNodeFavoriteId(1L, NodeType.EVENT, NODE_KEY)))
				.willReturn(true);

		GraphNodeDetailResponse response = graphNodeService.getNodeDetail(NodeType.EVENT, NODE_KEY, 1L);

		assertThat(response.nodeType()).isEqualTo("EVENT");
		assertThat(response.nodeKey()).isEqualTo(NODE_KEY);
		assertThat(response.title()).isEqualTo("한국은행 기준금리 동결");
		assertThat(response.type()).isNull();
		assertThat(response.time()).isEqualTo(TIME);
		assertThat(response.bookmarked()).isTrue();
	}

	@Test
	void 로그인_사용자가_즐겨찾기하지_않은_노드는_bookmarked_false다() {
		given(graphNodeRepository.findNode(NodeType.ENTITY, NODE_KEY))
				.willReturn(Optional.of(new GraphNodeRecord("한국은행", "GOVERNMENT_AGENCY", null)));
		given(userNodeFavoriteRepository.existsById(new UserNodeFavoriteId(1L, NodeType.ENTITY, NODE_KEY)))
				.willReturn(false);

		GraphNodeDetailResponse response = graphNodeService.getNodeDetail(NodeType.ENTITY, NODE_KEY, 1L);

		assertThat(response.type()).isEqualTo("GOVERNMENT_AGENCY");
		assertThat(response.time()).isNull();
		assertThat(response.bookmarked()).isFalse();
	}

	@Test
	void 비로그인_사용자는_즐겨찾기를_조회하지_않고_bookmarked_false다() {
		given(graphNodeRepository.findNode(NodeType.EVENT, NODE_KEY))
				.willReturn(Optional.of(new GraphNodeRecord("제목", null, TIME)));

		GraphNodeDetailResponse response = graphNodeService.getNodeDetail(NodeType.EVENT, NODE_KEY, null);

		assertThat(response.bookmarked()).isFalse();
		verifyNoInteractions(userNodeFavoriteRepository);
	}

	@Test
	void 노드가_없으면_RESOURCE_NOT_FOUND_예외() {
		given(graphNodeRepository.findNode(NodeType.EVENT, NODE_KEY)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> graphNodeService.getNodeDetail(NodeType.EVENT, NODE_KEY, 1L));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.RESOURCE_NOT_FOUND);
		verify(userNodeFavoriteRepository, never()).existsById(org.mockito.ArgumentMatchers.any());
	}

	@Test
	void Neo4j_조회가_실패하면_GRAPH_NODE_QUERY_FAILED_예외() {
		given(graphNodeRepository.findNode(NodeType.EVENT, NODE_KEY))
				.willThrow(new RuntimeException("bolt connection failed"));

		Throwable thrown = catchThrowable(() -> graphNodeService.getNodeDetail(NodeType.EVENT, NODE_KEY, 1L));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.GRAPH_NODE_QUERY_FAILED);
	}
}

package com.starlightnews.backend.domain.graph.service;

import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.graph.dto.GraphNeighborsResponse;
import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.graph.repository.GraphNeighborRepository;
import com.starlightnews.backend.domain.graph.repository.GraphNodeRecord;
import com.starlightnews.backend.domain.graph.repository.GraphNodeRepository;
import com.starlightnews.backend.domain.graph.repository.NeighborEdge;
import com.starlightnews.backend.domain.graph.repository.NeighborNode;
import com.starlightnews.backend.domain.graph.support.NeighborCursor;
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
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class GraphNeighborServiceTest {

	@Mock
	private GraphNodeRepository graphNodeRepository;

	@Mock
	private GraphNeighborRepository graphNeighborRepository;

	@InjectMocks
	private GraphNeighborService graphNeighborService;

	private static final String CENTER_KEY = "00000024-0920-4000-8000-000000000001";

	private GraphNodeRecord center(String title) {
		return new GraphNodeRecord(title, null, null);
	}

	private NeighborNode nb(String nodeType, String nodeKey, String label, double score) {
		return new NeighborNode(nodeType, nodeKey, label, score);
	}

	private NeighborEdge edge(String sourceKey, String targetKey, String type, double weight) {
		return new NeighborEdge(sourceKey, targetKey, type, weight);
	}

	private ErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 정상_조회는_이웃을_점수순으로_돌려주고_엣지를_노드집합으로_채운다() {
		given(graphNodeRepository.findNode(NodeType.ENTITY, CENTER_KEY))
				.willReturn(Optional.of(center("한국은행")));
		given(graphNeighborRepository.findNeighbors(NodeType.ENTITY, CENTER_KEY, 1, 300))
				.willReturn(List.of(
						nb("EVENT", "event-1", "기준금리 동결", 0.9),
						nb("STATEMENT", "stmt-1", "3분기 인하 예상", 0.4)));
		given(graphNeighborRepository.findEdges(any()))
				.willReturn(List.of(edge(CENTER_KEY, "event-1", "ACTOR", 0.9)));

		GraphNeighborsResponse response = graphNeighborService.getNeighbors(
				NodeType.ENTITY, CENTER_KEY, 1, 15, null);

		assertThat(response.centerNode().nodeType()).isEqualTo("ENTITY");
		assertThat(response.centerNode().nodeKey()).isEqualTo(CENTER_KEY);
		assertThat(response.centerNode().label()).isEqualTo("한국은행");
		assertThat(response.nodes()).extracting(GraphNeighborsResponse.NodeSummary::nodeKey)
				.containsExactly("event-1", "stmt-1");
		assertThat(response.edges()).singleElement().satisfies(e -> {
			assertThat(e.sourceNodeType()).isEqualTo("ENTITY");
			assertThat(e.sourceNodeKey()).isEqualTo(CENTER_KEY);
			assertThat(e.targetNodeType()).isEqualTo("EVENT");
			assertThat(e.targetNodeKey()).isEqualTo("event-1");
			assertThat(e.edgeType()).isEqualTo("ACTOR");
		});
		assertThat(response.returnedCount()).isEqualTo(2);
		assertThat(response.hasNext()).isFalse();
		assertThat(response.nextCursor()).isNull();
	}

	@Test
	void 이웃이_limit보다_많으면_hasNext_true이고_nextCursor를_만든다() {
		given(graphNodeRepository.findNode(any(NodeType.class), eq(CENTER_KEY)))
				.willReturn(Optional.of(center("한국은행")));
		given(graphNeighborRepository.findNeighbors(any(), any(), anyInt(), anyInt()))
				.willReturn(List.of(
						nb("EVENT", "a", "A", 0.9),
						nb("EVENT", "b", "B", 0.8),
						nb("ENTITY", "c", "C", 0.7)));
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of());

		GraphNeighborsResponse response = graphNeighborService.getNeighbors(
				NodeType.ENTITY, CENTER_KEY, 1, 2, null);

		assertThat(response.nodes()).hasSize(2);
		assertThat(response.hasNext()).isTrue();
		NeighborCursor decoded = NeighborCursor.decode(response.nextCursor());
		assertThat(decoded.neighborScore()).isEqualTo(0.8);
		assertThat(decoded.nodeType()).isEqualTo("EVENT");
		assertThat(decoded.nodeKey()).isEqualTo("b");
	}

	@Test
	void 커서가_있으면_그_정렬_위치_다음부터_돌려준다() {
		given(graphNodeRepository.findNode(any(NodeType.class), eq(CENTER_KEY)))
				.willReturn(Optional.of(center("한국은행")));
		given(graphNeighborRepository.findNeighbors(any(), any(), anyInt(), anyInt()))
				.willReturn(List.of(
						nb("EVENT", "a", "A", 0.9),
						nb("EVENT", "b", "B", 0.8),
						nb("ENTITY", "c", "C", 0.7),
						nb("STATEMENT", "d", "D", 0.6)));
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of());
		String cursor = new NeighborCursor(0.8, "EVENT", "b").encode();

		GraphNeighborsResponse response = graphNeighborService.getNeighbors(
				NodeType.ENTITY, CENTER_KEY, 1, 10, cursor);

		assertThat(response.nodes()).extracting(GraphNeighborsResponse.NodeSummary::nodeKey)
				.containsExactly("c", "d");
		assertThat(response.hasNext()).isFalse();
	}

	@Test
	void 잘못된_커서면_INVALID_CURSOR이고_Neo4j를_건드리지_않는다() {
		Throwable thrown = catchThrowable(() -> graphNeighborService.getNeighbors(
				NodeType.ENTITY, CENTER_KEY, 1, 15, "!!!not-base64!!!"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.INVALID_CURSOR);
		verifyNoInteractions(graphNodeRepository, graphNeighborRepository);
	}

	@Test
	void 중심_Node가_없으면_RESOURCE_NOT_FOUND이고_이웃은_조회하지_않는다() {
		given(graphNodeRepository.findNode(NodeType.ENTITY, CENTER_KEY)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> graphNeighborService.getNeighbors(
				NodeType.ENTITY, CENTER_KEY, 1, 15, null));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.RESOURCE_NOT_FOUND);
		verify(graphNeighborRepository, never()).findNeighbors(any(), any(), anyInt(), anyInt());
	}

	@Test
	void Neo4j_조회가_실패하면_GRAPH_NODE_QUERY_FAILED() {
		given(graphNodeRepository.findNode(any(NodeType.class), eq(CENTER_KEY)))
				.willThrow(new RuntimeException("bolt connection failed"));

		Throwable thrown = catchThrowable(() -> graphNeighborService.getNeighbors(
				NodeType.ENTITY, CENTER_KEY, 1, 15, null));

		assertThat(errorCodeOf(thrown)).isEqualTo(GraphErrorCode.GRAPH_NODE_QUERY_FAILED);
	}

	@Test
	void 엣지_양끝_중_응답_노드집합에_없는_키가_있으면_제외한다() {
		given(graphNodeRepository.findNode(any(NodeType.class), eq(CENTER_KEY)))
				.willReturn(Optional.of(center("한국은행")));
		given(graphNeighborRepository.findNeighbors(any(), any(), anyInt(), anyInt()))
				.willReturn(List.of(nb("EVENT", "a", "A", 0.9)));
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of(
				edge(CENTER_KEY, "a", "ACTOR", 0.9),
				edge("a", "not-in-page", "CAUSES", 0.7)));

		GraphNeighborsResponse response = graphNeighborService.getNeighbors(
				NodeType.ENTITY, CENTER_KEY, 1, 15, null);

		assertThat(response.edges()).singleElement()
				.satisfies(e -> assertThat(e.targetNodeKey()).isEqualTo("a"));
	}

	@Test
	void 이웃이_없으면_빈_목록과_hasNext_false이고_엣지는_조회하지_않는다() {
		given(graphNodeRepository.findNode(any(NodeType.class), eq(CENTER_KEY)))
				.willReturn(Optional.of(center("한국은행")));
		given(graphNeighborRepository.findNeighbors(any(), any(), anyInt(), anyInt()))
				.willReturn(List.of());

		GraphNeighborsResponse response = graphNeighborService.getNeighbors(
				NodeType.ENTITY, CENTER_KEY, 1, 15, null);

		assertThat(response.nodes()).isEmpty();
		assertThat(response.edges()).isEmpty();
		assertThat(response.returnedCount()).isZero();
		assertThat(response.hasNext()).isFalse();
		assertThat(response.nextCursor()).isNull();
		verify(graphNeighborRepository, never()).findEdges(any());
	}
}

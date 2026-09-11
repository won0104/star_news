package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

import com.starlightnews.backend.domain.graph.repository.GraphNeighborRepository;
import com.starlightnews.backend.domain.graph.repository.NeighborEdge;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse;
import com.starlightnews.backend.domain.user.dto.PersonalGraphSummaryResponse;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.domain.user.exception.PersonalGraphErrorCode;
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
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class PersonalGraphServiceTest {

	@Mock
	private UserKnowledgeNodeRepository userKnowledgeNodeRepository;

	@Mock
	private ArticleReadRepository articleReadRepository;

	@Mock
	private GraphNeighborRepository graphNeighborRepository;

	@InjectMocks
	private PersonalGraphService personalGraphService;

	private UserKnowledgeNode row(NodeType nodeType, String nodeId, String label, int readCount, int clickCount) {
		return row(nodeType, nodeId, label, "ECONOMY", readCount, clickCount);
	}

	private UserKnowledgeNode row(NodeType nodeType, String nodeId, String label, String topicCode,
			int readCount, int clickCount) {
		UserKnowledgeNode node = UserKnowledgeNode.forFirstClick(
				new UserKnowledgeNodeId(1L, nodeType, nodeId), label, topicCode,
				LocalDateTime.of(2024, 5, 25, 5, 20));
		ReflectionTestUtils.setField(node, "readArticleCount", readCount);
		ReflectionTestUtils.setField(node, "nodeClickCount", clickCount);
		return node;
	}

	private ArticleReadRepository.TopicReadCount topicReadCount(String topicCode, long count) {
		return new ArticleReadRepository.TopicReadCount() {
			@Override
			public String getTopicCode() {
				return topicCode;
			}

			@Override
			public long getCount() {
				return count;
			}
		};
	}

	private ErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 정상_조회는_MySQL_노드에_weight를_정규화하고_Neo4j_엣지를_조합한다() {
		given(userKnowledgeNodeRepository.findByUserIdAndTopicCode(1L, "ECONOMY")).willReturn(List.of(
				row(NodeType.ENTITY, "e1", "한국은행", 8, 2),
				row(NodeType.EVENT, "ev1", "기준금리 동결", 4, 0)));
		given(graphNeighborRepository.findEdges(any()))
				.willReturn(List.of(new NeighborEdge("e1", "ev1", "ACTOR", 0.82)));

		PersonalGraphMapResponse response = personalGraphService.getTopicMap(1L, "ECONOMY");

		assertThat(response.topic().topicCode()).isEqualTo("ECONOMY");
		assertThat(response.topic().label()).isEqualTo("경제");
		assertThat(response.generatedAt()).isNotNull();

		assertThat(response.nodes()).extracting(PersonalGraphMapResponse.Node::id)
				.containsExactly("ENTITY:e1", "EVENT:ev1");
		PersonalGraphMapResponse.Node entity = response.nodes().get(0);
		assertThat(entity.label()).isEqualTo("한국은행");
		assertThat(entity.sourceArticleCount()).isEqualTo(8);
		assertThat(entity.weight()).isEqualTo(1.0);            // (8+2) / max 10
		assertThat(response.nodes().get(1).weight()).isEqualTo(0.4); // (4+0) / 10

		assertThat(response.edges()).singleElement().satisfies(edge -> {
			assertThat(edge.sourceId()).isEqualTo("ENTITY:e1");
			assertThat(edge.targetId()).isEqualTo("EVENT:ev1");
			assertThat(edge.relationship()).isEqualTo("ACTOR");
			assertThat(edge.weight()).isEqualTo(0.82);
		});
	}

	@Test
	void 없는_topicCode면_INVALID_TOPIC_CODE이고_아무것도_조회하지_않는다() {
		Throwable thrown = catchThrowable(() -> personalGraphService.getTopicMap(1L, "NOT_A_TOPIC"));

		assertThat(errorCodeOf(thrown)).isEqualTo(PersonalGraphErrorCode.INVALID_TOPIC_CODE);
		verifyNoInteractions(userKnowledgeNodeRepository, graphNeighborRepository);
	}

	@Test
	void 개인_노드가_없으면_빈_목록이고_findEdges를_호출하지_않는다() {
		given(userKnowledgeNodeRepository.findByUserIdAndTopicCode(1L, "ECONOMY")).willReturn(List.of());

		PersonalGraphMapResponse response = personalGraphService.getTopicMap(1L, "ECONOMY");

		assertThat(response.nodes()).isEmpty();
		assertThat(response.edges()).isEmpty();
		verify(graphNeighborRepository, never()).findEdges(any());
	}

	@Test
	void display_유형이_아닌_노드는_제외한다() {
		given(userKnowledgeNodeRepository.findByUserIdAndTopicCode(1L, "ECONOMY")).willReturn(List.of(
				row(NodeType.ENTITY, "e1", "한국은행", 3, 1),
				row(NodeType.TOPIC, "t1", "경제토픽", 9, 9)));
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of());

		PersonalGraphMapResponse response = personalGraphService.getTopicMap(1L, "ECONOMY");

		assertThat(response.nodes()).extracting(PersonalGraphMapResponse.Node::nodeKey).containsExactly("e1");
	}

	@Test
	void 엣지_양끝_중_노드집합에_없는_키는_제외한다() {
		given(userKnowledgeNodeRepository.findByUserIdAndTopicCode(1L, "ECONOMY")).willReturn(List.of(
				row(NodeType.ENTITY, "e1", "한국은행", 5, 0),
				row(NodeType.EVENT, "ev1", "기준금리 동결", 2, 0)));
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of(
				new NeighborEdge("e1", "ev1", "ACTOR", 0.8),
				new NeighborEdge("e1", "ghost", "CAUSES", 0.7)));

		PersonalGraphMapResponse response = personalGraphService.getTopicMap(1L, "ECONOMY");

		assertThat(response.edges()).singleElement()
				.satisfies(edge -> assertThat(edge.targetId()).isEqualTo("EVENT:ev1"));
	}

	@Test
	void Neo4j_엣지_조회가_실패하면_INTERNAL_SERVER_ERROR() {
		given(userKnowledgeNodeRepository.findByUserIdAndTopicCode(1L, "ECONOMY")).willReturn(List.of(
				row(NodeType.ENTITY, "e1", "한국은행", 5, 0)));
		given(graphNeighborRepository.findEdges(any()))
				.willThrow(new RuntimeException("bolt connection failed"));

		Throwable thrown = catchThrowable(() -> personalGraphService.getTopicMap(1L, "ECONOMY"));

		assertThat(errorCodeOf(thrown)).isEqualTo(CommonErrorCode.INTERNAL_SERVER_ERROR);
	}

	// --- 요약 조회 ---

	private PersonalGraphSummaryResponse.Node nodeById(PersonalGraphSummaryResponse response, String id) {
		return response.nodes().stream()
				.filter(node -> node.id().equals(id))
				.findFirst()
				.orElseThrow();
	}

	@Test
	void 정상_요약_조회는_Topic별_클러스터와_대표_노드를_만들고_실제_엣지를_조합한다() {
		given(userKnowledgeNodeRepository.findByUserId(1L)).willReturn(List.of(
				row(NodeType.ENTITY, "e1", "한국은행", "ECONOMY", 8, 2),
				row(NodeType.EVENT, "ev1", "기준금리 동결", "ECONOMY", 4, 0),
				row(NodeType.EVENT, "ev2", "의대 증원", "SOCIETY", 2, 0)));
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of(
				topicReadCount("ECONOMY", 20), topicReadCount("SOCIETY", 5)));
		given(graphNeighborRepository.findEdges(any()))
				.willReturn(List.of(new NeighborEdge("e1", "ev1", "ACTOR", 0.8)));

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		assertThat(response.nodes()).hasSize(5);
		assertThat(nodeById(response, "topic:ECONOMY")).satisfies(node -> {
			assertThat(node.kind()).isEqualTo("TOPIC_CLUSTER");
			assertThat(node.title()).isEqualTo("경제");
			assertThat(node.sourceArticleCount()).isEqualTo(20);
			assertThat(node.weight()).isEqualTo(1.0);
		});
		assertThat(nodeById(response, "topic:SOCIETY").weight()).isEqualTo(0.25);
		assertThat(nodeById(response, "ENTITY:e1").weight()).isEqualTo(1.0);
		assertThat(nodeById(response, "EVENT:ev1").weight()).isEqualTo(0.4);
		assertThat(nodeById(response, "EVENT:ev2").weight()).isEqualTo(0.2);

		assertThat(response.edges()).hasSize(4);
		assertThat(response.edges()).filteredOn(edge -> edge.relationship().equals("BELONGS_TO_TOPIC")).hasSize(3);
		assertThat(response.edges()).anySatisfy(edge -> {
			assertThat(edge.sourceId()).isEqualTo("ENTITY:e1");
			assertThat(edge.targetId()).isEqualTo("EVENT:ev1");
			assertThat(edge.relationship()).isEqualTo("ACTOR");
		});
	}

	@Test
	void 대표_노드는_Topic당_최대_5개이고_읽은_기사가_없으면_클러스터_weight는_0이다() {
		List<UserKnowledgeNode> rows = new ArrayList<>();
		for (int i = 1; i <= 6; i++) {
			rows.add(row(NodeType.EVENT, "ev" + i, "이벤트" + i, "ECONOMY", 7 - i, 0)); // 중요도 6,5,4,3,2,1
		}
		given(userKnowledgeNodeRepository.findByUserId(1L)).willReturn(rows);
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of());
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of());

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		List<String> nodeKeys = response.nodes().stream()
				.filter(node -> node.kind().equals("NODE"))
				.map(PersonalGraphSummaryResponse.Node::nodeKey)
				.toList();
		assertThat(nodeKeys).hasSize(5).containsExactlyInAnyOrder("ev1", "ev2", "ev3", "ev4", "ev5");
		assertThat(nodeById(response, "topic:ECONOMY").weight()).isZero();
		assertThat(nodeById(response, "topic:ECONOMY").sourceArticleCount()).isZero();
	}

	@Test
	void topicCode가_없는_노드는_클러스터에_포함되지_않는다() {
		given(userKnowledgeNodeRepository.findByUserId(1L)).willReturn(List.of(
				row(NodeType.ENTITY, "e1", "한국은행", null, 5, 0),
				row(NodeType.EVENT, "ev1", "기준금리 동결", "ECONOMY", 3, 0)));
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of());
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of());

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		assertThat(response.nodes()).extracting(PersonalGraphSummaryResponse.Node::id)
				.containsExactlyInAnyOrder("topic:ECONOMY", "EVENT:ev1");
	}

	@Test
	void display_유형이_아닌_노드는_요약에서_제외한다() {
		given(userKnowledgeNodeRepository.findByUserId(1L)).willReturn(List.of(
				row(NodeType.TOPIC, "t1", "경제토픽", "ECONOMY", 9, 9),
				row(NodeType.ENTITY, "e1", "한국은행", "ECONOMY", 3, 0)));
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of());
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of());

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		assertThat(response.nodes()).extracting(PersonalGraphSummaryResponse.Node::id)
				.containsExactlyInAnyOrder("topic:ECONOMY", "ENTITY:e1");
	}

	@Test
	void 개인_노드가_없으면_빈_배열이고_외부_조회를_하지_않는다() {
		given(userKnowledgeNodeRepository.findByUserId(1L)).willReturn(List.of());

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		assertThat(response.nodes()).isEmpty();
		assertThat(response.edges()).isEmpty();
		verify(articleReadRepository, never()).countReadArticlesByTopic(any());
		verify(graphNeighborRepository, never()).findEdges(any());
	}

	@Test
	void 요약_엣지_양끝_중_대표_노드가_아닌_키는_제외한다() {
		given(userKnowledgeNodeRepository.findByUserId(1L)).willReturn(List.of(
				row(NodeType.ENTITY, "e1", "한국은행", "ECONOMY", 5, 0),
				row(NodeType.EVENT, "ev1", "기준금리 동결", "ECONOMY", 3, 0)));
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of());
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of(
				new NeighborEdge("e1", "ev1", "ACTOR", 0.8),
				new NeighborEdge("e1", "ghost", "CAUSES", 0.7)));

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		long realEdgeCount = response.edges().stream()
				.filter(edge -> !edge.relationship().equals("BELONGS_TO_TOPIC"))
				.count();
		assertThat(realEdgeCount).isEqualTo(1);
	}
}

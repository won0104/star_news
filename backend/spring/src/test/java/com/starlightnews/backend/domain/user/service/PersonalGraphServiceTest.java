package com.starlightnews.backend.domain.user.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import com.starlightnews.backend.domain.graph.repository.GraphNeighborRepository;
import com.starlightnews.backend.domain.graph.repository.NeighborEdge;
import com.starlightnews.backend.domain.user.cache.ExploredNodeCountCache;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse;
import com.starlightnews.backend.domain.user.dto.PersonalGraphSummaryResponse;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository;
import com.starlightnews.backend.domain.user.repository.UserKnowledgeNodeRepository.TopicNodeCount;
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
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
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

	@Mock
	private ExploredNodeCountCache exploredNodeCountCache;

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

	private TopicNodeCount topicNodeCount(String topicCode, long count) {
		return new TopicNodeCount() {
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

	/** getSummary 는 Topic 7개 전부를 조회하므로, 언급 안 한 Topic 은 빈 목록이라는 기본값을 한 번만 깔아둔다. */
	private boolean representativeDefaultStubbed = false;

	/** 리포지토리가 이미 DB에서 상위 N개를 정렬해 돌려준다고 가정하고, 그 결과를 그대로 스텁한다. */
	private void stubRepresentatives(String topicCode, List<UserKnowledgeNode> rows) {
		if (!representativeDefaultStubbed) {
			given(userKnowledgeNodeRepository.findTopRepresentatives(eq(1L), any(), any(), anyInt()))
					.willReturn(List.of());
			representativeDefaultStubbed = true;
		}
		given(userKnowledgeNodeRepository.findTopRepresentatives(eq(1L), eq(topicCode), any(), anyInt()))
				.willReturn(rows);
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
		stubRepresentatives("ECONOMY", List.of(
				row(NodeType.ENTITY, "e1", "한국은행", "ECONOMY", 8, 2),
				row(NodeType.EVENT, "ev1", "기준금리 동결", "ECONOMY", 4, 0)));
		stubRepresentatives("SOCIETY", List.of(
				row(NodeType.EVENT, "ev2", "의대 증원", "SOCIETY", 2, 0)));
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of(
				topicReadCount("ECONOMY", 20), topicReadCount("SOCIETY", 5)));
		given(userKnowledgeNodeRepository.countExploredNodesByTopic(eq(1L), any()))
				.willReturn(List.of(topicNodeCount("ECONOMY", 1))); // e1 만 클릭함(clickCount>0)
		given(graphNeighborRepository.findEdges(any()))
				.willReturn(List.of(new NeighborEdge("e1", "ev1", "ACTOR", 0.8)));

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		// 7개 Topic 클러스터(대표 노드 없는 5개 포함) + 대표 노드 3개
		assertThat(response.nodes()).hasSize(10);
		assertThat(response.nodes()).filteredOn(node -> node.kind().equals("TOPIC_CLUSTER")).hasSize(7);
		assertThat(nodeById(response, "topic:ECONOMY")).satisfies(node -> {
			assertThat(node.kind()).isEqualTo("TOPIC_CLUSTER");
			assertThat(node.title()).isEqualTo("경제");
			assertThat(node.sourceArticleCount()).isEqualTo(20);
			assertThat(node.weight()).isEqualTo(1.0);
		});
		assertThat(nodeById(response, "topic:SOCIETY").weight()).isEqualTo(5.0 / 21); // (읽음5+탐색0) / (경제 읽음20+탐색1)
		assertThat(nodeById(response, "ENTITY:e1").weight()).isEqualTo(1.0);
		assertThat(nodeById(response, "EVENT:ev1").weight()).isEqualTo(0.4);
		assertThat(nodeById(response, "EVENT:ev2").weight()).isEqualTo(0.2);

		// 한 번도 안 읽은 Topic(POLITICS)도 대표 노드 없이 weight 0 클러스터로 나온다
		assertThat(nodeById(response, "topic:POLITICS")).satisfies(node -> {
			assertThat(node.sourceArticleCount()).isZero();
			assertThat(node.weight()).isZero();
		});
		assertThat(response.nodes()).filteredOn(node -> node.topicCode().equals("POLITICS")).hasSize(1);

		assertThat(response.edges()).hasSize(4);
		assertThat(response.edges()).filteredOn(edge -> edge.relationship().equals("BELONGS_TO_TOPIC")).hasSize(3);
		assertThat(response.edges()).anySatisfy(edge -> {
			assertThat(edge.sourceId()).isEqualTo("ENTITY:e1");
			assertThat(edge.targetId()).isEqualTo("EVENT:ev1");
			assertThat(edge.relationship()).isEqualTo("ACTOR");
		});
	}

	@Test
	void 참여도_집계가_캐시에_있으면_DB를_다시_세지_않고_캐시값을_그대로_쓴다() {
		given(exploredNodeCountCache.get(1L)).willReturn(Optional.of(Map.of("ECONOMY", 3L)));
		stubRepresentatives("ECONOMY", List.of(row(NodeType.ENTITY, "e1", "한국은행", "ECONOMY", 0, 0)));
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of());
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of());

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		assertThat(nodeById(response, "topic:ECONOMY").weight()).isEqualTo(1.0); // 캐시된 참여도 3 이 그대로 반영됨
		verify(userKnowledgeNodeRepository, never()).countExploredNodesByTopic(any(), any());
		verify(exploredNodeCountCache, never()).put(any(), any());
	}

	@Test
	void 참여도_집계가_캐시에_없으면_DB에서_계산해서_캐시에_채워넣는다() {
		given(exploredNodeCountCache.get(1L)).willReturn(Optional.empty());
		stubRepresentatives("ECONOMY", List.of(row(NodeType.ENTITY, "e1", "한국은행", "ECONOMY", 0, 0)));
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of());
		given(userKnowledgeNodeRepository.countExploredNodesByTopic(eq(1L), any()))
				.willReturn(List.of(topicNodeCount("ECONOMY", 4)));
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of());

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		assertThat(nodeById(response, "topic:ECONOMY").weight()).isEqualTo(1.0);
		verify(exploredNodeCountCache).put(1L, Map.of("ECONOMY", 4L));
	}

	@Test
	void 기사를_안읽고_노드만_클릭한_Topic도_weight가_0이_아니다() {
		stubRepresentatives("ECONOMY", List.of(
				row(NodeType.ENTITY, "e1", "한국은행", "ECONOMY", 0, 3),
				row(NodeType.EVENT, "ev1", "기준금리 동결", "ECONOMY", 0, 2)));
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of()); // 읽은 기사 없음
		given(userKnowledgeNodeRepository.countExploredNodesByTopic(eq(1L), any()))
				.willReturn(List.of(topicNodeCount("ECONOMY", 2))); // e1, ev1 둘 다 클릭함
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of());

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		PersonalGraphSummaryResponse.Node economy = nodeById(response, "topic:ECONOMY");
		assertThat(economy.sourceArticleCount()).isZero(); // 화면 표시 숫자는 여전히 "읽은 기사 수"만
		assertThat(economy.weight()).isEqualTo(1.0); // 탐색한 서로 다른 노드 2개가 유일한 참여 신호
	}

	@Test
	void 요약은_리포지토리가_돌려준_대표_노드_순서_그대로_사용한다() {
		// Topic당 상위 N개 정렬·절단은 UserKnowledgeNodeRepository.findTopRepresentatives(DB 쿼리)가 담당한다.
		// (정렬·LIMIT 자체의 검증은 UserKnowledgeNodeRepositoryTest 에서 한다.)
		stubRepresentatives("ECONOMY", List.of(
				row(NodeType.EVENT, "ev1", "이벤트1", "ECONOMY", 6, 0),
				row(NodeType.EVENT, "ev2", "이벤트2", "ECONOMY", 5, 0),
				row(NodeType.EVENT, "ev3", "이벤트3", "ECONOMY", 4, 0),
				row(NodeType.EVENT, "ev4", "이벤트4", "ECONOMY", 3, 0),
				row(NodeType.EVENT, "ev5", "이벤트5", "ECONOMY", 2, 0)));
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of());
		given(graphNeighborRepository.findEdges(any())).willReturn(List.of());

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		List<String> nodeKeys = response.nodes().stream()
				.filter(node -> node.kind().equals("NODE"))
				.map(PersonalGraphSummaryResponse.Node::nodeKey)
				.toList();
		assertThat(nodeKeys).containsExactly("ev1", "ev2", "ev3", "ev4", "ev5");
		assertThat(nodeById(response, "topic:ECONOMY").weight()).isZero();
		assertThat(nodeById(response, "topic:ECONOMY").sourceArticleCount()).isZero();
	}

	@Test
	void 개인_노드가_없어도_Topic_7개는_빈_클러스터로_반환되고_Neo4j는_조회하지_않는다() {
		// findTopRepresentatives/countExploredNodesByTopic 은 스텁 없이도 기본값(빈 목록)을 반환한다.
		given(articleReadRepository.countReadArticlesByTopic(1L)).willReturn(List.of());

		PersonalGraphSummaryResponse response = personalGraphService.getSummary(1L);

		assertThat(response.nodes()).hasSize(7);
		assertThat(response.nodes()).allSatisfy(node -> {
			assertThat(node.kind()).isEqualTo("TOPIC_CLUSTER");
			assertThat(node.sourceArticleCount()).isZero();
			assertThat(node.weight()).isZero();
		});
		assertThat(response.edges()).isEmpty();
		verify(graphNeighborRepository, never()).findEdges(any());
	}

	@Test
	void 요약_엣지_양끝_중_대표_노드가_아닌_키는_제외한다() {
		stubRepresentatives("ECONOMY", List.of(
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

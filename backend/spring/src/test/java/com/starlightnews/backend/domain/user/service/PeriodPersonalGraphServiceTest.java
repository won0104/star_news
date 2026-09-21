package com.starlightnews.backend.domain.user.service;

import java.time.LocalDate;
import java.util.List;

import com.starlightnews.backend.domain.graph.repository.GraphNeighborRepository;
import com.starlightnews.backend.domain.graph.repository.NeighborEdge;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository;
import com.starlightnews.backend.domain.user.repository.ArticleReadRepository.GraphReadRow;
import com.starlightnews.backend.domain.user.repository.PeriodGraphNodeRef;
import com.starlightnews.backend.domain.user.repository.PeriodGraphNodeRepository;
import com.starlightnews.backend.domain.user.support.GraphReadPeriod;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.enums.TopicCode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class PeriodPersonalGraphServiceTest {

	@Mock private ArticleReadRepository articleReadRepository;
	@Mock private PeriodGraphNodeRepository periodGraphNodeRepository;
	@Mock private GraphNeighborRepository graphNeighborRepository;
	@InjectMocks private PeriodPersonalGraphService service;

	private static final GraphReadPeriod PERIOD = new GraphReadPeriod(
			LocalDate.of(2026, 9, 1), LocalDate.of(2026, 9, 30));

	private GraphReadRow read(String key, String topicCode) {
		GraphReadRow row = mock(GraphReadRow.class);
		given(row.getArticleNodeKey()).willReturn(key);
		given(row.getTopicCode()).willReturn(topicCode);
		return row;
	}

	@Test
	void 기간_내_읽은_기사만_집계하고_중복_관계는_한_번만_센다() {
		GraphReadRow firstRead = read("article-1", "ECONOMY");
		GraphReadRow secondRead = read("article-2", "ECONOMY");
		given(articleReadRepository.findGraphReadsInPeriod(1L,
				PERIOD.fromInclusive(), PERIOD.toExclusive()))
				.willReturn(List.of(firstRead, secondRead));
		given(periodGraphNodeRepository.findConnectedNodes(List.of("article-1", "article-2")))
				.willReturn(List.of(
					new PeriodGraphNodeRef("article-1", NodeType.EVENT, "event-1", "사건", "ECONOMY"),
					new PeriodGraphNodeRef("article-1", NodeType.EVENT, "event-1", "사건", "ECONOMY"),
					new PeriodGraphNodeRef("article-2", NodeType.EVENT, "event-1", "사건", "ECONOMY"),
					new PeriodGraphNodeRef("article-2", NodeType.ENTITY, "entity-1", "기관", "ECONOMY")));
		given(graphNeighborRepository.findEdges(org.mockito.ArgumentMatchers.anyCollection()))
				.willReturn(List.of(
					new NeighborEdge("event-1", "entity-1", "ACTOR", 0.8),
					new NeighborEdge("event-1", "outside", "RELATED", 0.7)));

		var summary = service.getSummary(1L, PERIOD);
		var map = service.getTopicMap(1L, "ECONOMY", PERIOD);

		assertThat(summary.nodes()).hasSize(TopicCode.values().length + 2);
		assertThat(summary.nodes().stream().filter(node -> "topic:ECONOMY".equals(node.id()))
				.findFirst().orElseThrow().sourceArticleCount()).isEqualTo(2);
		assertThat(map.nodes()).extracting(node -> node.sourceArticleCount()).containsExactly(2, 1);
		assertThat(map.edges()).extracting(edge -> edge.relationship()).containsExactly("ACTOR");
	}

	@Test
	void 기간에_읽은_기사가_없으면_빈_클러스터만_반환한다() {
		given(articleReadRepository.findGraphReadsInPeriod(1L,
				PERIOD.fromInclusive(), PERIOD.toExclusive())).willReturn(List.of());

		var summary = service.getSummary(1L, PERIOD);

		assertThat(summary.nodes()).hasSize(TopicCode.values().length);
		assertThat(summary.nodes()).allSatisfy(node -> assertThat(node.sourceArticleCount()).isZero());
		assertThat(summary.edges()).isEmpty();
		verify(periodGraphNodeRepository, never()).findConnectedNodes(org.mockito.ArgumentMatchers.anyCollection());
	}
}

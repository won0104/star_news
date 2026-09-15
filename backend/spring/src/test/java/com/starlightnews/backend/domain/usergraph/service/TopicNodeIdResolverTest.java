package com.starlightnews.backend.domain.usergraph.service;

import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.usergraph.repository.TopicNodeIdRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class TopicNodeIdResolverTest {

	private static final String ECONOMY_NODE_ID = "00000126-1001-4000-8000-000000000001";
	private static final String SPORTS_NODE_ID = "00000126-1002-4000-8000-000000000002";

	@Mock
	private TopicNodeIdRepository topicNodeIdRepository;

	@InjectMocks
	private TopicNodeIdResolver resolver;

	@Test
	void Topic_코드를_nodeId로_바꾼다() {
		given(topicNodeIdRepository.findAllTopicNodeIds())
				.willReturn(Map.of("ECONOMY", ECONOMY_NODE_ID, "SPORTS", SPORTS_NODE_ID));

		assertThat(resolver.toNodeIds(List.of("ECONOMY", "SPORTS")))
				.containsExactlyInAnyOrder(ECONOMY_NODE_ID, SPORTS_NODE_ID);
	}

	@Test
	void 대응하는_Topic이_없는_코드는_결과에서_뺀다() {
		// 없는 nodeId 를 보내면 FastAPI 에서 매칭되지 않고 조용히 사라진다. 보내기 전에 거른다.
		given(topicNodeIdRepository.findAllTopicNodeIds())
				.willReturn(Map.of("ECONOMY", ECONOMY_NODE_ID));

		assertThat(resolver.toNodeIds(List.of("ECONOMY", "UNKNOWN_TOPIC")))
				.containsExactly(ECONOMY_NODE_ID);
	}

	@Test
	void 빈_목록이면_Neo4j를_조회하지_않는다() {
		assertThat(resolver.toNodeIds(List.of())).isEmpty();

		verify(topicNodeIdRepository, times(0)).findAllTopicNodeIds();
	}

	@Test
	void 한_번_읽은_대응표는_다시_조회하지_않는다() {
		// 고정 Topic 은 바뀌지 않는다. 회차마다 사용자 수만큼 변환하므로 매번 조회할 이유가 없다.
		given(topicNodeIdRepository.findAllTopicNodeIds())
				.willReturn(Map.of("ECONOMY", ECONOMY_NODE_ID));

		resolver.toNodeIds(List.of("ECONOMY"));
		resolver.toNodeIds(List.of("ECONOMY"));

		verify(topicNodeIdRepository, times(1)).findAllTopicNodeIds();
	}

	@Test
	void 조회에_실패하면_빈_결과를_주고_다음에_다시_시도한다() {
		// 실패를 캐싱하면 재기동 전까지 Topic 관심이 영영 비어 버린다.
		given(topicNodeIdRepository.findAllTopicNodeIds())
				.willThrow(new IllegalStateException("Neo4j unavailable"))
				.willReturn(Map.of("ECONOMY", ECONOMY_NODE_ID));

		assertThat(resolver.toNodeIds(List.of("ECONOMY"))).isEmpty();
		assertThat(resolver.toNodeIds(List.of("ECONOMY"))).containsExactly(ECONOMY_NODE_ID);
	}

	@Test
	void 고정_Topic이_비어_있으면_캐싱하지_않는다() {
		// 그래프 마이그레이션이 아직 안 돌았을 수 있다.
		given(topicNodeIdRepository.findAllTopicNodeIds())
				.willReturn(Map.of())
				.willReturn(Map.of("ECONOMY", ECONOMY_NODE_ID));

		assertThat(resolver.toNodeIds(List.of("ECONOMY"))).isEmpty();
		assertThat(resolver.toNodeIds(List.of("ECONOMY"))).containsExactly(ECONOMY_NODE_ID);
	}

	@Test
	void Topic_관심이_없어도_회차는_계속된다() {
		// 동기화 전체를 실패시키지 않는다는 계약을 고정한다.
		given(topicNodeIdRepository.findAllTopicNodeIds())
				.willThrow(new IllegalStateException("Neo4j unavailable"));

		assertThat(resolver.toNodeIds(List.of("ECONOMY", "SPORTS"))).isEmpty();
	}
}

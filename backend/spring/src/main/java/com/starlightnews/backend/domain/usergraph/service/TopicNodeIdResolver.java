package com.starlightnews.backend.domain.usergraph.service;

import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import com.starlightnews.backend.domain.usergraph.repository.TopicNodeIdRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * Topic 코드를 User Graph 동기화가 요구하는 nodeId 로 바꾼다.
 *
 * <p>고정 Topic 7개는 그래프 마이그레이션이 심어 둔 뒤로 바뀌지 않으므로 한 번 읽어 캐싱한다.
 * 회차마다 모든 사용자의 관심 Topic 을 변환하는데 그때마다 Neo4j 를 때릴 이유가 없다.
 *
 * <p>조회에 실패하거나 결과가 비면 캐싱하지 않는다. 그래프가 아직 준비되지 않았을 수 있고,
 * 그 상태를 캐싱해 버리면 재기동 전까지 Topic 관심이 영영 비어 버린다.
 */
@Slf4j
@Component
public class TopicNodeIdResolver {

	private final TopicNodeIdRepository topicNodeIdRepository;
	private final AtomicReference<Map<String, String>> cached = new AtomicReference<>();

	public TopicNodeIdResolver(TopicNodeIdRepository topicNodeIdRepository) {
		this.topicNodeIdRepository = topicNodeIdRepository;
	}

	/**
	 * Topic 코드 목록을 nodeId 목록으로 바꾼다.
	 *
	 * <p>대응하는 Topic 노드를 찾지 못한 코드는 결과에서 빠진다. 없는 nodeId 를 보내도 FastAPI 쪽에서
	 * 매칭되지 않고 조용히 사라지므로, 보내기 전에 거른다.
	 */
	public List<String> toNodeIds(Collection<String> topicCodes) {
		if (topicCodes.isEmpty()) {
			return List.of();
		}

		Map<String, String> nodeIdsByCode = nodeIdsByCode();
		List<String> nodeIds = topicCodes.stream()
				.map(nodeIdsByCode::get)
				.filter(java.util.Objects::nonNull)
				.toList();

		if (nodeIds.size() < topicCodes.size()) {
			log.warn("Topic nodeId 를 찾지 못한 코드가 있습니다. (요청 {}건, 변환 {}건)",
					topicCodes.size(), nodeIds.size());
		}
		return nodeIds;
	}

	private Map<String, String> nodeIdsByCode() {
		Map<String, String> current = cached.get();
		if (current != null) {
			return current;
		}

		Map<String, String> loaded = load();
		if (loaded.isEmpty()) {
			return loaded;
		}
		cached.compareAndSet(null, loaded);
		return cached.get();
	}

	private Map<String, String> load() {
		try {
			Map<String, String> loaded = topicNodeIdRepository.findAllTopicNodeIds();
			if (loaded.isEmpty()) {
				log.warn("Neo4j 에서 고정 Topic 을 찾지 못했습니다. 이번 회차는 Topic 관심 없이 동기화합니다.");
			}
			return loaded;
		} catch (RuntimeException unavailable) {
			// Topic 관심만 비우고 나머지 동기화는 진행한다. 회차 전체를 실패시킬 이유가 없다.
			log.warn("Topic nodeId 조회에 실패했습니다. (원인={})", unavailable.getMessage());
			return Map.of();
		}
	}
}

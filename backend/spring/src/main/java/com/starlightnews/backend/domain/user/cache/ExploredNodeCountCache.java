package com.starlightnews.backend.domain.user.cache;

import java.util.Map;
import java.util.Optional;

/**
 * 개인 그래프 요약(getSummary)의 Topic 별 참여(클릭) Node 개수 캐시.
 * {@code UserKnowledgeNodeRepository#countExploredNodesByTopic} 은 사용자의 전체 개인 Node 를
 * 한 번은 훑어야 나오는 값이라(LIMIT으로 줄일 수 없는 집계), 자주 안 바뀌는데 매 요청마다 다시
 * 계산하는 비용이 크다. 무효화는 {@code GraphNodeClickService} 가 클릭을 기록할 때 담당한다.
 */
public interface ExploredNodeCountCache {

	Optional<Map<String, Long>> get(Long userId);

	void put(Long userId, Map<String, Long> countByTopic);

	void evict(Long userId);
}

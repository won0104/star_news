package com.starlightnews.backend.domain.user.cache;

import java.util.Map;
import java.util.Optional;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * 캐시 비활성 기본 구현 (app.cache.store=none, 기본값). 항상 미스 처리해서 매번 DB 로 계산한다.
 * Redis 가 없는 로컬/테스트/CI 환경에서도 개인 그래프 요약 조회가 그대로 동작해야 하기 때문에 기본값이다.
 */
@Component
@ConditionalOnProperty(name = "app.cache.store", havingValue = "none", matchIfMissing = true)
public class NoOpExploredNodeCountCache implements ExploredNodeCountCache {

	@Override
	public Optional<Map<String, Long>> get(Long userId) {
		return Optional.empty();
	}

	@Override
	public void put(Long userId, Map<String, Long> countByTopic) {
		// 캐시 비활성 상태이므로 아무것도 하지 않는다.
	}

	@Override
	public void evict(Long userId) {
		// 캐시 비활성 상태이므로 아무것도 하지 않는다.
	}
}

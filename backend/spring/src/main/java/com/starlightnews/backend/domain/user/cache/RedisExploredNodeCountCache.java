package com.starlightnews.backend.domain.user.cache;

import java.time.Duration;
import java.util.Map;
import java.util.Optional;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/**
 * Redis 기반 캐시. 키: personal-graph:explored-count:{userId}, 값: {topicCode: count} JSON 문자열.
 * 무효화는 GraphNodeClickService 가 클릭마다 evict 하는 걸 기본으로 삼되, 놓치는 경우를 대비해
 * 짧은 안전망 TTL 도 같이 둔다. app.cache.store=redis 일 때 사용된다.
 */
@Component
@ConditionalOnProperty(name = "app.cache.store", havingValue = "redis")
public class RedisExploredNodeCountCache implements ExploredNodeCountCache {

	private static final String KEY_PREFIX = "personal-graph:explored-count:";
	private static final Duration SAFETY_TTL = Duration.ofHours(1);

	private final StringRedisTemplate redis;
	private final ObjectMapper objectMapper;

	public RedisExploredNodeCountCache(StringRedisTemplate redis, ObjectMapper objectMapper) {
		this.redis = redis;
		this.objectMapper = objectMapper;
	}

	@Override
	public Optional<Map<String, Long>> get(Long userId) {
		String raw = redis.opsForValue().get(KEY_PREFIX + userId);
		if (raw == null) {
			return Optional.empty();
		}
		try {
			return Optional.of(objectMapper.readValue(raw, new TypeReference<Map<String, Long>>() {
			}));
		} catch (JsonProcessingException exception) {
			return Optional.empty(); // 손상된 캐시 값은 미스로 취급하고 DB에서 다시 계산한다.
		}
	}

	@Override
	public void put(Long userId, Map<String, Long> countByTopic) {
		try {
			redis.opsForValue().set(KEY_PREFIX + userId, objectMapper.writeValueAsString(countByTopic), SAFETY_TTL);
		} catch (JsonProcessingException exception) {
			// 직렬화 실패해도 이번 응답은 이미 계산돼 나간 값이라 무시한다 — 다음 요청이 다시 계산할 뿐이다.
		}
	}

	@Override
	public void evict(Long userId) {
		redis.delete(KEY_PREFIX + userId);
	}
}

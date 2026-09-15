package com.starlightnews.backend.domain.usergraph.repository;

import java.util.Map;

/**
 * 고정 Topic 의 {@code topicCode → nodeId} 대응을 Neo4j 에서 읽는다.
 *
 * <p>MySQL 은 Topic 을 코드(예: {@code ECONOMY})로 다루지만 User Graph 동기화는 nodeId(UUID)를 요구한다.
 * 그 사이를 메우기 위한 조회다.
 */
public interface TopicNodeIdRepository {

	/**
	 * 모든 고정 Topic 의 코드와 nodeId 를 조회한다.
	 *
	 * @return topicCode 를 키로 하는 대응표. 조회하지 못하면 빈 Map
	 */
	Map<String, String> findAllTopicNodeIds();
}

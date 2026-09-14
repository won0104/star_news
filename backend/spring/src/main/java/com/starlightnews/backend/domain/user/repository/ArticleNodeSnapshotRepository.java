package com.starlightnews.backend.domain.user.repository;

import java.util.List;

/**
 * 기사에 연결된 개인 지식 Node 조회. (열람 기록 저장 시 user_knowledge_nodes 를 채우는 입력)
 */
public interface ArticleNodeSnapshotRepository {

	/**
	 * Neo4j Article Node 에 직접(1홉) 연결된 EVENT·ENTITY·STATEMENT Node 를 모두 가져온다.
	 * 해당 Article Node 가 없거나 연결 Node 가 없으면 빈 목록.
	 */
	List<ArticleNodeSnapshot> findConnectedNodes(String articleNodeKey);
}

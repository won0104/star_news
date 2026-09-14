package com.starlightnews.backend.domain.user.repository;

import com.starlightnews.backend.global.enums.NodeType;

/**
 * 기사 하나에 연결된 개인 지식 Node 를 Neo4j 에서 스냅샷으로 가져온 값.
 * label 은 화면 표시 이름(항상 존재), topicCode 는 그 Node 의 대표 서비스 Topic 이며 없으면 null(ENTITY·STATEMENT).
 */
public record ArticleNodeSnapshot(NodeType nodeType, String nodeKey, String label, String topicCode) {
}

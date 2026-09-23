package com.starlightnews.backend.domain.user.repository;

import com.starlightnews.backend.global.enums.NodeType;

/**
 * 기사 하나에 연결된 개인 지식 Node 를 Neo4j 에서 스냅샷으로 가져온 값.
 * label 은 화면 표시 이름(항상 존재), topicCode 는 그 Node 의 대표 서비스 Topic 이며 없으면 null(ENTITY·STATEMENT).
 *
 * <p>primary 는 이 기사가 그 Node 를 대표로 다뤘는지다({@code COVERS.isPrimary}). 기사 한 건이 사건
 * 열 개 넘게 이어지는 일이 흔한데 대부분은 스치듯 언급된 부차 사건이라, 추천에서 "본 것"으로 칠지
 * 가를 때 쓴다. Event 가 아닌 Node 는 항상 false 다.
 */
public record ArticleNodeSnapshot(NodeType nodeType, String nodeKey, String label, String topicCode,
		boolean primary) {
}

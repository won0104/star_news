package com.starlightnews.backend.domain.user.repository;

/**
 * 개인 Node 를 새로 만들 때 Neo4j 에서 스냅샷으로 가져오는 값.
 * label 은 화면 표시 이름(항상 존재), topicCode 는 대표 서비스 Topic 이며 없으면 null(ENTITY·STATEMENT).
 */
public record NodeSnapshot(String label, String topicCode) {
}

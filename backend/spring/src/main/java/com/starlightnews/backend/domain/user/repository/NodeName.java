package com.starlightnews.backend.domain.user.repository;

/** Neo4j Node의 업무 식별자와 화면 표시 이름. */
public record NodeName(String nodeId, String name) {
}

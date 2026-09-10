package com.starlightnews.backend.global.enums;

import java.util.Optional;

/**
 * 사용자 탐색·지식 그래프에서 참조하는 Node 유형.
 * Neo4j User 추천이기 때문에 따로 포함 X
 * 각 유형은 Neo4j Label과, 화면 표시용으로 뽑아낼 속성 이름을 함께 가진다.
 */
public enum NodeType {

	ARTICLE("Article", "title", null, "publishedAt"),
	EVENT("Event", "title", null, "occurredAt"),
	STORY("Story", "title", null, "lastEventAt"),
	TOPIC("Topic", "nameKo", null, null),
	ENTITY("Entity", "canonicalName", "entityType", null),

	TIME("Time", "value", "granularity", null),
	STATEMENT("Statement", "text", "statementType", null);

	private final String label;
	private final String titleProperty;
	private final String typeProperty;
	private final String timeProperty;

	NodeType(String label, String titleProperty, String typeProperty, String timeProperty) {
		this.label = label;
		this.titleProperty = titleProperty;
		this.typeProperty = typeProperty;
		this.timeProperty = timeProperty;
	}

	/** Neo4j Node Label. */
	public String label() {
		return label;
	}

	/** API 응답 title 로 변환할 Node 이름 속성. */
	public String titleProperty() {
		return titleProperty;
	}

	/** Entity·Statement 의 세부 유형 또는 Time 의 시간 단위 속성. 없으면 null. */
	public String typeProperty() {
		return typeProperty;
	}

	/** Event 발생 시각 또는 Story 대표 시각 속성. 없으면 null. */
	public String timeProperty() {
		return timeProperty;
	}

	/**
	 * 문자열을 NodeType 으로 변환한다. 앞뒤 공백과 대소문자는 허용한다.
	 * 허용되지 않는 값이면 빈 Optional 을 반환하며, 예외 변환은 호출 측에서 담당한다.
	 */
	public static Optional<NodeType> from(String value) {
		if (value == null || value.isBlank()) {
			return Optional.empty();
		}

		String normalized = value.strip().toUpperCase();
		for (NodeType type : values()) {
			if (type.name().equals(normalized)) {
				return Optional.of(type);
			}
		}
		return Optional.empty();
	}
}

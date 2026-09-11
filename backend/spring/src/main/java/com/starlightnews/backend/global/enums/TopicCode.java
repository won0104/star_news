package com.starlightnews.backend.global.enums;

import java.util.Optional;

/**
 * 뉴스 기사·Event·Story 및 사용자 관심 분야의 대분류 코드.
 * DB(user_interest.topic_code, articles.topic_code 등)에는 상수 이름을 문자열로 저장한다.
 */
public enum TopicCode {

	POLITICS("정치"),
	ECONOMY("경제"),
	SOCIETY("사회"),
	CULTURE("문화"),
	INTERNATIONAL("국제"),
	SPORTS("스포츠"),
	IT_SCIENCE("IT·과학");

	private final String labelKo;

	TopicCode(String labelKo) {
		this.labelKo = labelKo;
	}

	/** 화면 표시용 한글 분류명 (Neo4j Topic.nameKo 와 동일). */
	public String labelKo() {
		return labelKo;
	}

	/**
	 * 문자열 코드를 TopicCode로 변환한다. 앞뒤 공백과 대소문자는 허용한다.
	 * 허용되지 않는 값이면 빈 Optional을 반환하며, 예외 변환은 호출 측에서 담당한다.
	 */
	public static Optional<TopicCode> from(String code) {
		if (code == null || code.isBlank()) {
			return Optional.empty();
		}

		String normalized = code.strip().toUpperCase();
		for (TopicCode topicCode : values()) {
			if (topicCode.name().equals(normalized)) {
				return Optional.of(topicCode);
			}
		}
		return Optional.empty();
	}
}

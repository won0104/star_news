package com.starlightnews.backend.global.enums;

import java.util.Optional;

/**
 * 뉴스 기사·Event·Story 및 사용자 관심 분야의 대분류 코드.
 * DB(user_interest.topic_code, articles.topic_code 등)에는 상수 이름을 문자열로 저장한다.
 */
public enum TopicCode {

	POLITICS,
	ECONOMY,
	SOCIETY,
	CULTURE,
	INTERNATIONAL,
	SPORTS,
	IT_SCIENCE;

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

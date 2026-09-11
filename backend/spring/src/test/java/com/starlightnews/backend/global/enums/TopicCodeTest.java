package com.starlightnews.backend.global.enums;

import java.util.Optional;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class TopicCodeTest {

	@Test
	void from_유효한코드는_해당_상수를_반환한다() {
		assertThat(TopicCode.from("ECONOMY")).contains(TopicCode.ECONOMY);
		assertThat(TopicCode.from("IT_SCIENCE")).contains(TopicCode.IT_SCIENCE);
	}

	@Test
	void from_존재하지_않는_코드는_빈_Optional을_반환한다() {
		assertThat(TopicCode.from("SPORTS_ENTERTAINMENT")).isEmpty();
		assertThat(TopicCode.from("unknown")).isEmpty();
	}

	@Test
	void from_null이나_공백은_빈_Optional을_반환한다() {
		assertThat(TopicCode.from(null)).isEmpty();
		assertThat(TopicCode.from(" ")).isEmpty();
	}

	@Test
	void from_대소문자와_앞뒤_공백을_허용한다() {
		assertThat(TopicCode.from("  economy  ")).contains(TopicCode.ECONOMY);
	}

	@Test
	void 모든_상수는_7개이며_이름과_코드가_일치한다() {
		assertThat(TopicCode.values()).hasSize(7);
		for (TopicCode topicCode : TopicCode.values()) {
			assertThat(TopicCode.from(topicCode.name())).contains(topicCode);
		}
	}

	@Test
	void from의_반환타입은_Optional이다() {
		Optional<TopicCode> result = TopicCode.from("POLITICS");
		assertThat(result).isPresent();
	}

	@Test
	void labelKo는_상수마다_한글_분류명을_반환한다() {
		assertThat(TopicCode.ECONOMY.labelKo()).isEqualTo("경제");
		assertThat(TopicCode.IT_SCIENCE.labelKo()).isEqualTo("IT·과학");
		for (TopicCode topicCode : TopicCode.values()) {
			assertThat(topicCode.labelKo()).isNotBlank();
		}
	}
}

package com.starlightnews.backend.global.enums;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class InterestTypeTest {

	@Test
	void 관심과_비관심_두_값을_가진다() {
		assertThat(InterestType.values())
				.containsExactlyInAnyOrder(InterestType.INTEREST, InterestType.DISLIKE);
	}

	@Test
	void 상수_이름은_DB에_저장되는_문자열과_동일하다() {
		assertThat(InterestType.INTEREST.name()).isEqualTo("INTEREST");
		assertThat(InterestType.DISLIKE.name()).isEqualTo("DISLIKE");
	}
}

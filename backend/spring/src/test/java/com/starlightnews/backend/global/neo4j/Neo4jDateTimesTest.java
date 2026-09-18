package com.starlightnews.backend.global.neo4j;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;

import org.junit.jupiter.api.Test;
import org.neo4j.driver.Values;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class Neo4jDateTimesTest {

	private static final ZoneOffset KST = ZoneOffset.ofHours(9);
	private static final OffsetDateTime EXPECTED = OffsetDateTime.of(2026, 9, 17, 10, 33, 23, 0, KST);

	@Test
	void 시간대가_붙은_값을_그대로_읽는다() {
		ZonedDateTime zoned = ZonedDateTime.of(2026, 9, 17, 10, 33, 23, 0, KST);

		assertThat(Neo4jDateTimes.toOffsetDateTime(Values.value(zoned))).isEqualTo(EXPECTED);
	}

	@Test
	void 지역_이름_시간대도_오프셋으로_읽는다() {
		ZonedDateTime zoned = ZonedDateTime.of(2026, 9, 17, 10, 33, 23, 0, ZoneId.of("Asia/Seoul"));

		assertThat(Neo4jDateTimes.toOffsetDateTime(Values.value(zoned))).isEqualTo(EXPECTED);
	}

	@Test
	void 시간대가_없는_값은_KST_로_본다() {
		// 발행 시각에 오프셋을 붙이기 전에 분석된 기사가 LOCAL DATETIME 으로 남아 있었다.
		LocalDateTime local = LocalDateTime.of(2026, 9, 17, 10, 33, 23);

		assertThat(Neo4jDateTimes.toOffsetDateTime(Values.value(local))).isEqualTo(EXPECTED);
	}

	@Test
	void 오프셋이_붙은_문자열을_읽는다() {
		// 일괄 적재한 기사는 발행 시각이 ISO 문자열로 들어가 있었다.
		assertThat(Neo4jDateTimes.toOffsetDateTime(Values.value("2026-09-17T10:33:23+09:00")))
				.isEqualTo(EXPECTED);
	}

	@Test
	void 오프셋이_없는_문자열은_KST_로_본다() {
		assertThat(Neo4jDateTimes.toOffsetDateTime(Values.value("2026-09-17T10:33:23")))
				.isEqualTo(EXPECTED);
	}

	@Test
	void 값이_없으면_null_이다() {
		assertThat(Neo4jDateTimes.toOffsetDateTime(Values.NULL)).isNull();
		assertThat(Neo4jDateTimes.toOffsetDateTime(null)).isNull();
	}

	@Test
	void 시각이_아닌_문자열이면_원인을_담아_실패한다() {
		assertThatThrownBy(() -> Neo4jDateTimes.toOffsetDateTime(Values.value("어제")))
				.isInstanceOf(IllegalStateException.class)
				.hasMessageContaining("어제");
	}

	@Test
	void 시각이_아닌_타입이면_실패한다() {
		assertThatThrownBy(() -> Neo4jDateTimes.toOffsetDateTime(Values.value(42L)))
				.isInstanceOf(IllegalStateException.class)
				.hasMessageContaining("INTEGER");
	}
}

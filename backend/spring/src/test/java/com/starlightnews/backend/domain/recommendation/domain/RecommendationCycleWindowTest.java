package com.starlightnews.backend.domain.recommendation.domain;

import java.time.LocalDateTime;

import com.starlightnews.backend.global.enums.RecommendationCycle;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

class RecommendationCycleWindowTest {

	@Test
	void 오전_계산은_당일_06시에_공개한다() {
		var window = RecommendationCycleWindow.from(LocalDateTime.of(2026, 9, 15, 5, 30));

		assertThat(window.cycle()).isEqualTo(RecommendationCycle.AM);
		assertThat(window.availableAt()).isEqualTo(LocalDateTime.of(2026, 9, 15, 6, 0));
	}

	@Test
	void 오후_계산은_당일_18시에_공개한다() {
		var window = RecommendationCycleWindow.from(LocalDateTime.of(2026, 9, 15, 17, 30));

		assertThat(window.cycle()).isEqualTo(RecommendationCycle.PM);
		assertThat(window.availableAt()).isEqualTo(LocalDateTime.of(2026, 9, 15, 18, 0));
	}

	@Test
	void 계산_시각은_그대로_보관한다() {
		LocalDateTime recommendedAt = LocalDateTime.of(2026, 9, 15, 5, 30, 12);

		assertThat(RecommendationCycleWindow.from(recommendedAt).recommendedAt())
				.isEqualTo(recommendedAt);
	}

	@ParameterizedTest
	@CsvSource({
			"00:30, AM", "05:30, AM", "11:59, AM",
			"12:00, PM", "17:30, PM", "23:50, PM"
	})
	void 정오를_기준으로_회차를_가른다(String time, RecommendationCycle expected) {
		// 정해진 시각에 돌지 않아도 회차가 하나로 정해져야 재시도 때 같은 회차를 덮어쓴다.
		LocalDateTime recommendedAt = LocalDateTime.parse("2026-09-15T" + time + ":00");

		assertThat(RecommendationCycleWindow.from(recommendedAt).cycle()).isEqualTo(expected);
	}

	@Test
	void 배치가_늦으면_공개_시각이_이미_지나_있다() {
		// 06:10 에 끝났으면 06:00 으로 저장돼 즉시 공개된다.
		var window = RecommendationCycleWindow.from(LocalDateTime.of(2026, 9, 15, 6, 10));

		assertThat(window.availableAt()).isEqualTo(LocalDateTime.of(2026, 9, 15, 6, 0));
		assertThat(window.isReleasedImmediately()).isTrue();
	}

	@Test
	void 제_시간에_돌면_공개_시각이_아직_오지_않았다() {
		var window = RecommendationCycleWindow.from(LocalDateTime.of(2026, 9, 15, 5, 30));

		assertThat(window.isReleasedImmediately()).isFalse();
	}

	@Test
	void 자정_직후에_돌아도_당일_오전_회차다() {
		// 날짜가 넘어가지 않아야 한다. 전날 회차로 잡히면 이미 지난 회차를 덮어쓴다.
		var window = RecommendationCycleWindow.from(LocalDateTime.of(2026, 9, 15, 0, 30));

		assertThat(window.cycle()).isEqualTo(RecommendationCycle.AM);
		assertThat(window.availableAt()).isEqualTo(LocalDateTime.of(2026, 9, 15, 6, 0));
	}

	@Test
	void 늦은_밤에_돌아도_당일_오후_회차다() {
		var window = RecommendationCycleWindow.from(LocalDateTime.of(2026, 9, 15, 23, 50));

		assertThat(window.cycle()).isEqualTo(RecommendationCycle.PM);
		assertThat(window.availableAt()).isEqualTo(LocalDateTime.of(2026, 9, 15, 18, 0));
	}

	@Test
	void 같은_회차_안에서는_몇_번을_계산해도_공개_시각이_같다() {
		// 재시도가 같은 회차를 덮어쓰려면 공개 시각이 키로 안정적이어야 한다.
		var first = RecommendationCycleWindow.from(LocalDateTime.of(2026, 9, 15, 5, 30));
		var retry = RecommendationCycleWindow.from(LocalDateTime.of(2026, 9, 15, 5, 47));

		assertThat(retry.availableAt()).isEqualTo(first.availableAt());
		assertThat(retry.cycle()).isEqualTo(first.cycle());
	}
}

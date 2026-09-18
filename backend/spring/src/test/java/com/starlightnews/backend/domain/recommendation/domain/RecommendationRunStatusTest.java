package com.starlightnews.backend.domain.recommendation.domain;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class RecommendationRunStatusTest {

	@Test
	void 실패한_묶음이_없으면_완료다() {
		assertThat(RecommendationRunStatus.of(3, 0)).isEqualTo(RecommendationRunStatus.COMPLETED);
	}

	@Test
	void 일부만_실패하면_부분_완료다() {
		assertThat(RecommendationRunStatus.of(3, 1)).isEqualTo(RecommendationRunStatus.PARTIAL);
	}

	@Test
	void 전부_실패하면_실패다() {
		assertThat(RecommendationRunStatus.of(3, 3)).isEqualTo(RecommendationRunStatus.FAILED);
	}

	@Test
	void 대상_사용자가_없던_회차는_완료다() {
		// 가입자가 없는 초기 환경. 실패로 두면 할 일이 없었을 뿐인 회차가 장애처럼 보인다.
		assertThat(RecommendationRunStatus.of(0, 0)).isEqualTo(RecommendationRunStatus.COMPLETED);
	}
}

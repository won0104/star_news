package com.starlightnews.backend.domain.recommendation.repository;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import com.starlightnews.backend.global.enums.RecommendationType;
import com.starlightnews.backend.support.TestFixtures;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class UserRecommendationRepositoryTest {

	private static final String EVENT_ID = "00000128-1001-4000-8000-000000000001";
	private static final String OTHER_EVENT_ID = "00000128-1002-4000-8000-000000000002";

	private static final LocalDateTime RECOMMENDED_AT = LocalDateTime.of(2026, 9, 15, 5, 30);
	private static final LocalDateTime AVAILABLE_AT = LocalDateTime.of(2026, 9, 15, 6, 0);

	@Autowired
	private UserRecommendationRepository repository;

	@Autowired
	private RecommendationEventRepository eventRepository;

	@Autowired
	private TestEntityManager entityManager;

	@BeforeEach
	void insertReferencedRows() {
		TestFixtures.insertUsers(entityManager, 1L, 2L);
		// user_recommendations 는 recommendation_events 를 참조한다. 먼저 있어야 한다.
		eventRepository.upsert(EVENT_ID, "기준금리 동결", "ECONOMY");
		eventRepository.upsert(OTHER_EVENT_ID, "반도체 지원 발표", "IT_SCIENCE");
		entityManager.flush();
	}

	private UserRecommendation recommendation(long userId, String eventId, int rank,
			RecommendationType type, LocalDateTime availableAt) {
		return new UserRecommendation(userId, eventId, type,
				new BigDecimal("0.920000"), (short) rank,
				RECOMMENDED_AT, RecommendationCycle.AM, availableAt);
	}

	private void saveAndFlush(UserRecommendation recommendation) {
		repository.save(recommendation);
		entityManager.flush();
	}

	@Test
	void 추천_결과를_저장하고_순위순으로_조회한다() {
		saveAndFlush(recommendation(1L, OTHER_EVENT_ID, 2, RecommendationType.NORMAL, AVAILABLE_AT));
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));

		List<UserRecommendation> found =
				repository.findByUserIdAndAvailableAtOrderByRankAsc(1L, AVAILABLE_AT);

		assertThat(found).extracting(UserRecommendation::getEventId)
				.containsExactly(EVENT_ID, OTHER_EVENT_ID);
	}

	@Test
	void 저장한_값이_그대로_돌아온다() {
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));
		entityManager.clear();

		UserRecommendation found =
				repository.findByUserIdAndAvailableAtOrderByRankAsc(1L, AVAILABLE_AT).get(0);

		assertThat(found.getUserRecommendationId()).isNotNull();
		assertThat(found.getRecommendationType()).isEqualTo(RecommendationType.COLD_START);
		assertThat(found.getRecommendationScore()).isEqualByComparingTo("0.920000");
		assertThat(found.getRank()).isEqualTo((short) 1);
		assertThat(found.getCycle()).isEqualTo(RecommendationCycle.AM);
		assertThat(found.getRecommendedAt()).isEqualTo(RECOMMENDED_AT);
		assertThat(found.getAvailableAt()).isEqualTo(AVAILABLE_AT);
	}

	@Test
	void 같은_회차에_같은_순위를_두_번_넣을_수_없다() {
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));

		assertThatThrownBy(() -> saveAndFlush(
				recommendation(1L, OTHER_EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT)))
				.isInstanceOf(Exception.class);
	}

	@Test
	void 같은_회차에_같은_Event를_두_번_넣을_수_없다() {
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));

		assertThatThrownBy(() -> saveAndFlush(
				recommendation(1L, EVENT_ID, 2, RecommendationType.COLD_START, AVAILABLE_AT)))
				.isInstanceOf(Exception.class);
	}

	@Test
	void 유형이_다르면_같은_순위를_쓸_수_있다() {
		// 유니크 제약이 유형을 포함하므로, 관심 기반 1위와 지식 공백 1위가 함께 존재할 수 있다.
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));
		saveAndFlush(recommendation(1L, OTHER_EVENT_ID, 1, RecommendationType.NORMAL, AVAILABLE_AT));

		assertThat(repository.findByUserIdAndAvailableAtOrderByRankAsc(1L, AVAILABLE_AT)).hasSize(2);
	}

	@Test
	void 사용자가_다르면_같은_순위를_쓸_수_있다() {
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));
		saveAndFlush(recommendation(2L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));

		assertThat(repository.findByUserIdAndAvailableAtOrderByRankAsc(2L, AVAILABLE_AT)).hasSize(1);
	}

	@Test
	void 회차를_지우면_해당_사용자의_그_회차만_사라진다() {
		LocalDateTime previousCycle = AVAILABLE_AT.minusHours(12);
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, previousCycle));
		saveAndFlush(recommendation(2L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));

		assertThat(repository.deleteCycle(List.of(1L), AVAILABLE_AT)).isEqualTo(1);
		entityManager.clear();

		assertThat(repository.findByUserIdAndAvailableAtOrderByRankAsc(1L, AVAILABLE_AT)).isEmpty();
		assertThat(repository.findByUserIdAndAvailableAtOrderByRankAsc(1L, previousCycle)).hasSize(1);
		assertThat(repository.findByUserIdAndAvailableAtOrderByRankAsc(2L, AVAILABLE_AT)).hasSize(1);
	}

	@Test
	void 회차를_비우면_같은_순위를_다시_넣을_수_있다() {
		// 재시도로 같은 회차를 다시 저장하는 경우다.
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));

		repository.deleteCycle(List.of(1L), AVAILABLE_AT);
		entityManager.flush();
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));

		assertThat(repository.findByUserIdAndAvailableAtOrderByRankAsc(1L, AVAILABLE_AT)).hasSize(1);
	}

	@Test
	void 기준_시각과_정확히_같은_회차는_남긴다() {
		// 경계에서 하루치가 통째로 사라지지 않도록 고정한다.
		LocalDateTime threshold = AVAILABLE_AT.minusDays(7);
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, threshold));

		assertThat(repository.deleteOlderThan(threshold)).isZero();
		entityManager.clear();

		assertThat(repository.findByUserIdAndAvailableAtOrderByRankAsc(1L, threshold)).hasSize(1);
	}

	@Test
	void 보관_기간이_지난_회차를_지운다() {
		LocalDateTime old = AVAILABLE_AT.minusDays(8);
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, old));
		saveAndFlush(recommendation(1L, EVENT_ID, 1, RecommendationType.COLD_START, AVAILABLE_AT));

		assertThat(repository.deleteOlderThan(AVAILABLE_AT.minusDays(7))).isEqualTo(1);
		entityManager.clear();

		assertThat(repository.findByUserIdAndAvailableAtOrderByRankAsc(1L, old)).isEmpty();
		assertThat(repository.findByUserIdAndAvailableAtOrderByRankAsc(1L, AVAILABLE_AT)).hasSize(1);
	}
}

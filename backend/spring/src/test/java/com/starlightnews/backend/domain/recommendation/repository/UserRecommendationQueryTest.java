package com.starlightnews.backend.domain.recommendation.repository;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import com.starlightnews.backend.global.enums.RecommendationType;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 추천 보드 조회 쿼리를 실제 MySQL 에서 확인한다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class UserRecommendationQueryTest {

	private static final long USER_ID = 97_100L;
	private static final long OTHER_USER_ID = 97_200L;
	private static final LocalDateTime AM = LocalDateTime.of(2026, 9, 16, 6, 0);
	private static final LocalDateTime PM = LocalDateTime.of(2026, 9, 16, 18, 0);

	@Autowired
	private UserRecommendationRepository repository;

	@Autowired
	private EntityManager entityManager;

	@BeforeEach
	void insertFixtures() {
		// 테스트 DB 가 실제 MySQL 이라 user_id·event_id 외래키가 그대로 강제된다.
		for (long userId : new long[] {USER_ID, OTHER_USER_ID}) {
			entityManager.createNativeQuery("INSERT INTO users (user_id, login_id, password_hash, nickname) "
							+ "VALUES (?1, ?2, 'hashed-password', ?3) "
							+ "ON DUPLICATE KEY UPDATE user_id = user_id")
					.setParameter(1, userId)
					.setParameter(2, "board-user-" + userId)
					.setParameter(3, "보드사용자" + userId)
					.executeUpdate();
		}
		for (int seed = 1; seed <= 3; seed++) {
			entityManager.createNativeQuery("INSERT INTO recommendation_events "
							+ "(event_id, title, topic_code, summary_status) "
							+ "VALUES (?1, ?2, 'ECONOMY', 'NOT_REQUESTED') "
							+ "ON DUPLICATE KEY UPDATE event_id = event_id")
					.setParameter(1, eventId(seed))
					.setParameter(2, "기준금리 동결 " + seed)
					.executeUpdate();
		}
		entityManager.flush();
	}

	private UserRecommendation save(long userId, String eventId, short rank,
			RecommendationType type, LocalDateTime availableAt) {
		UserRecommendation saved = repository.save(new UserRecommendation(userId, eventId, type,
				new BigDecimal("0.900000"), rank, "테스트 근거",
				availableAt.minusMinutes(30),
				availableAt.getHour() < 12 ? RecommendationCycle.AM : RecommendationCycle.PM,
				availableAt));
		entityManager.flush();
		return saved;
	}

	private String eventId(int seed) {
		return String.format("00000020-0920-4000-8000-%012d", seed);
	}

	@Test
	void 공개된_회차_중_가장_최근_것을_고른다() {
		save(USER_ID, eventId(1), (short) 1, RecommendationType.INTEREST_BASED, AM);
		save(USER_ID, eventId(2), (short) 1, RecommendationType.INTEREST_BASED, PM);

		Optional<LocalDateTime> latest = repository.findLatestAvailableAt(USER_ID, PM.plusMinutes(1));

		assertThat(latest).contains(PM);
	}

	@Test
	void 아직_공개_시각이_안_된_회차는_고르지_않는다() {
		save(USER_ID, eventId(1), (short) 1, RecommendationType.INTEREST_BASED, AM);
		save(USER_ID, eventId(2), (short) 1, RecommendationType.INTEREST_BASED, PM);

		// 정오 기준으로는 오전 회차만 보여야 한다. 06:00·18:00 공개 규칙이 여기서 지켜진다.
		assertThat(repository.findLatestAvailableAt(USER_ID, PM.minusHours(6))).contains(AM);
	}

	@Test
	void 공개된_회차가_없으면_비어_있다() {
		save(USER_ID, eventId(1), (short) 1, RecommendationType.INTEREST_BASED, PM);

		assertThat(repository.findLatestAvailableAt(USER_ID, PM.minusMinutes(1))).isEmpty();
	}

	@Test
	void 남의_회차는_보이지_않는다() {
		save(OTHER_USER_ID, eventId(1), (short) 1, RecommendationType.INTEREST_BASED, PM);

		assertThat(repository.findLatestAvailableAt(USER_ID, PM.plusMinutes(1))).isEmpty();
	}

	@Test
	void 순위_오름차순으로_돌려준다() {
		save(USER_ID, eventId(3), (short) 3, RecommendationType.INTEREST_BASED, PM);
		save(USER_ID, eventId(1), (short) 1, RecommendationType.INTEREST_BASED, PM);
		save(USER_ID, eventId(2), (short) 2, RecommendationType.INTEREST_BASED, PM);

		List<UserRecommendation> page = repository.findCycle(USER_ID, PM);

		assertThat(page).extracting(UserRecommendation::getRank)
				.containsExactly((short) 1, (short) 2, (short) 3);
	}

	@Test
	void 같은_순위가_겹쳐도_빠짐없이_돌려준다() {
		// rank 는 유형 안에서만 유일하다. 두 유형이 한 회차에 들어오면 1위가 둘이다.
		save(USER_ID, eventId(1), (short) 1, RecommendationType.INTEREST_BASED, PM);
		save(USER_ID, eventId(2), (short) 1, RecommendationType.KNOWLEDGE_GAP, PM);

		assertThat(repository.findCycle(USER_ID, PM)).hasSize(2);
	}

	@Test
	void 순위가_같으면_ID_순으로_줄을_세운다() {
		UserRecommendation first = save(USER_ID, eventId(1), (short) 1,
				RecommendationType.INTEREST_BASED, PM);
		UserRecommendation second = save(USER_ID, eventId(2), (short) 1,
				RecommendationType.KNOWLEDGE_GAP, PM);

		assertThat(repository.findCycle(USER_ID, PM))
				.extracting(UserRecommendation::getUserRecommendationId)
				.containsExactly(first.getUserRecommendationId(), second.getUserRecommendationId());
	}

	@Test
	void 다른_회차는_섞이지_않는다() {
		save(USER_ID, eventId(1), (short) 1, RecommendationType.INTEREST_BASED, AM);
		save(USER_ID, eventId(2), (short) 1, RecommendationType.INTEREST_BASED, PM);

		List<UserRecommendation> page = repository.findCycle(USER_ID, PM);

		assertThat(page).extracting(UserRecommendation::getEventId).containsExactly(eventId(2));
	}
}

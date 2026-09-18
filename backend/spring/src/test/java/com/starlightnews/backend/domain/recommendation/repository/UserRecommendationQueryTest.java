package com.starlightnews.backend.domain.recommendation.repository;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunStatus;
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

	/** 끝난 회차로 저장한다. 실행 기록이 없으면 보드에 보이지 않는다. */
	private UserRecommendation save(long userId, String eventId, short rank,
			RecommendationType type, LocalDateTime availableAt) {
		run(availableAt, RecommendationRunStatus.COMPLETED);
		return saveWithoutRun(userId, eventId, rank, type, availableAt);
	}

	private void run(LocalDateTime availableAt, RecommendationRunStatus status) {
		entityManager.createNativeQuery("INSERT INTO recommendation_runs "
						+ "(cycle, available_at, status, started_at) VALUES (?1, ?2, ?3, ?4)")
				.setParameter(1, availableAt.getHour() < 12 ? "AM" : "PM")
				.setParameter(2, availableAt)
				.setParameter(3, status.name())
				.setParameter(4, availableAt.minusMinutes(30))
				.executeUpdate();
	}

	private Optional<LocalDateTime> latest(LocalDateTime now) {
		return repository.findLatestAvailableAt(USER_ID, now, RecommendationRunStatus.visible());
	}

	private UserRecommendation saveWithoutRun(long userId, String eventId, short rank,
			RecommendationType type, LocalDateTime availableAt) {
		UserRecommendation saved = repository.save(new UserRecommendation(userId, eventId, type,
				new BigDecimal("0.900000"), rank,
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
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, AM);
		save(USER_ID, eventId(2), (short) 1, RecommendationType.NORMAL, PM);

		Optional<LocalDateTime> latest = latest(PM.plusMinutes(1));

		assertThat(latest).contains(PM);
	}

	@Test
	void 아직_공개_시각이_안_된_회차는_고르지_않는다() {
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, AM);
		save(USER_ID, eventId(2), (short) 1, RecommendationType.NORMAL, PM);

		// 정오 기준으로는 오전 회차만 보여야 한다. 06:00·18:00 공개 규칙이 여기서 지켜진다.
		assertThat(latest(PM.minusHours(6))).contains(AM);
	}

	@Test
	void 공개된_회차가_없으면_비어_있다() {
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, PM);

		assertThat(latest(PM.minusMinutes(1))).isEmpty();
	}

	@Test
	void 남의_회차는_보이지_않는다() {
		save(OTHER_USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, PM);

		assertThat(latest(PM.plusMinutes(1))).isEmpty();
	}

	// --- 실행 상태에 따른 노출 ---

	@Test
	void 도는_중인_회차는_공개_시각이_지나도_고르지_않는다() {
		// 공개 시각을 넘겨 재시도 중이면 일부 사용자만 저장돼 있다. 직전 회차를 보여 준다.
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, AM);
		run(PM, RecommendationRunStatus.RUNNING);
		saveWithoutRun(USER_ID, eventId(2), (short) 1, RecommendationType.NORMAL, PM);

		assertThat(latest(PM.plusMinutes(1))).contains(AM);
	}

	@Test
	void 실패한_회차는_고르지_않는다() {
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, AM);
		run(PM, RecommendationRunStatus.FAILED);
		saveWithoutRun(USER_ID, eventId(2), (short) 1, RecommendationType.NORMAL, PM);

		assertThat(latest(PM.plusMinutes(1))).contains(AM);
	}

	@Test
	void 일부_묶음만_실패한_회차는_고른다() {
		// 저장된 사용자는 새 추천을 본다. 실패한 묶음의 사용자는 이 회차 행이 없어 직전 회차를 본다.
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, AM);
		run(PM, RecommendationRunStatus.PARTIAL);
		saveWithoutRun(USER_ID, eventId(2), (short) 1, RecommendationType.NORMAL, PM);

		assertThat(latest(PM.plusMinutes(1))).contains(PM);
	}

	@Test
	void 부분_완료_회차에서_빠진_사용자는_직전_회차를_본다() {
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, AM);
		run(PM, RecommendationRunStatus.PARTIAL);
		saveWithoutRun(OTHER_USER_ID, eventId(2), (short) 1, RecommendationType.NORMAL, PM);

		assertThat(latest(PM.plusMinutes(1))).contains(AM);
	}

	@Test
	void 실행_기록이_없는_회차는_고르지_않는다() {
		saveWithoutRun(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, PM);

		assertThat(latest(PM.plusMinutes(1))).isEmpty();
	}

	@Test
	void 같은_회차를_다시_돌려_한_번이라도_끝났으면_고른다() {
		// 수동 재실행. 앞 실행이 서버 종료로 RUNNING 에 멈춰 있어도 뒤 실행이 끝났으면 보여 준다.
		run(PM, RecommendationRunStatus.RUNNING);
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, PM);

		assertThat(latest(PM.plusMinutes(1))).contains(PM);
	}

	@Test
	void 순위_오름차순으로_돌려준다() {
		save(USER_ID, eventId(3), (short) 3, RecommendationType.NORMAL, PM);
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, PM);
		save(USER_ID, eventId(2), (short) 2, RecommendationType.NORMAL, PM);

		List<UserRecommendation> page = repository.findCycle(USER_ID, PM);

		assertThat(page).extracting(UserRecommendation::getRank)
				.containsExactly((short) 1, (short) 2, (short) 3);
	}

	@Test
	void 같은_순위가_겹쳐도_빠짐없이_돌려준다() {
		// DB 유니크 제약이 유형까지 묶여 있어 한 회차에 순위가 겹쳐도 막지 않는다.
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, PM);
		save(USER_ID, eventId(2), (short) 1, RecommendationType.COLD_START, PM);

		assertThat(repository.findCycle(USER_ID, PM)).hasSize(2);
	}

	@Test
	void 순위가_같으면_ID_순으로_줄을_세운다() {
		UserRecommendation first = save(USER_ID, eventId(1), (short) 1,
				RecommendationType.NORMAL, PM);
		UserRecommendation second = save(USER_ID, eventId(2), (short) 1,
				RecommendationType.COLD_START, PM);

		assertThat(repository.findCycle(USER_ID, PM))
				.extracting(UserRecommendation::getUserRecommendationId)
				.containsExactly(first.getUserRecommendationId(), second.getUserRecommendationId());
	}

	@Test
	void 다른_회차는_섞이지_않는다() {
		save(USER_ID, eventId(1), (short) 1, RecommendationType.NORMAL, AM);
		save(USER_ID, eventId(2), (short) 1, RecommendationType.NORMAL, PM);

		List<UserRecommendation> page = repository.findCycle(USER_ID, PM);

		assertThat(page).extracting(UserRecommendation::getEventId).containsExactly(eventId(2));
	}
}

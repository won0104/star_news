package com.starlightnews.backend.domain.recommendation.service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.ZoneId;

import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationBoardResponse;
import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import com.starlightnews.backend.global.enums.RecommendationType;
import com.starlightnews.backend.global.enums.TopicCode;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 추천 보드 조회 서비스.
 *
 * <p>회차 선택이 현재 시각에 달려 있다. 시계를 주입하지 않기로 했으므로 회차 시각을 지금 기준
 * 상대값으로 잡는다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class RecommendationBoardServiceTest {

	private static final long USER_ID = 96_100L;

	@Autowired
	private RecommendationBoardService boardService;

	@Autowired
	private UserRecommendationRepository userRecommendationRepository;

	@Autowired
	private EntityManager entityManager;

	/** 이미 공개된 회차. */
	private LocalDateTime opened;

	/** 아직 공개되지 않은 회차. */
	private LocalDateTime upcoming;

	@BeforeEach
	void insertFixtures() {
		LocalDateTime now = LocalDateTime.now(ZoneId.of("Asia/Seoul"));
		opened = now.minusHours(2).withNano(0);
		upcoming = now.plusHours(2).withNano(0);

		entityManager.createNativeQuery("INSERT INTO users (user_id, login_id, password_hash, nickname) "
						+ "VALUES (?1, 'board-service-user', 'hashed-password', '보드사용자') "
						+ "ON DUPLICATE KEY UPDATE user_id = user_id")
				.setParameter(1, USER_ID).executeUpdate();
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

	private String eventId(int seed) {
		return String.format("00000020-0920-4000-8000-%012d", seed);
	}

	private void save(int seed, short rank, RecommendationType type, LocalDateTime availableAt) {
		userRecommendationRepository.save(new UserRecommendation(USER_ID, eventId(seed), type,
				new BigDecimal("0.920000"), rank, "관심 Story 에서 아직 접하지 않은 사건입니다.",
				availableAt.minusMinutes(30), RecommendationCycle.PM, availableAt));
		entityManager.flush();
	}

	@Test
	void 공개된_회차를_순위_순으로_돌려준다() {
		save(2, (short) 2, RecommendationType.INTEREST_BASED, opened);
		save(1, (short) 1, RecommendationType.INTEREST_BASED, opened);

		RecommendationBoardResponse response = boardService.getBoard(USER_ID);

		assertThat(response.items()).extracting(RecommendationBoardResponse.Item::rank)
				.containsExactly((short) 1, (short) 2);
		assertThat(response.availableAt().toLocalDateTime()).isEqualTo(opened);
		assertThat(response.generatedAt().toLocalDateTime()).isEqualTo(opened.minusMinutes(30));
		assertThat(response.cycle()).isEqualTo(RecommendationCycle.PM);
	}

	@Test
	void 공개_시각이_안_된_회차는_보여주지_않는다() {
		// 계산은 05:30·17:30 에 끝나지만 공개는 06:00·18:00 이다. 그 사이에는 직전 회차가 보여야 한다.
		save(1, (short) 1, RecommendationType.INTEREST_BASED, opened);
		save(2, (short) 1, RecommendationType.KNOWLEDGE_GAP, upcoming);

		RecommendationBoardResponse response = boardService.getBoard(USER_ID);

		assertThat(response.availableAt().toLocalDateTime()).isEqualTo(opened);
		assertThat(response.items()).singleElement()
				.extracting(RecommendationBoardResponse.Item::eventId).isEqualTo(eventId(1));
	}

	@Test
	void 공개된_회차가_없으면_빈_응답이다() {
		// 신규 가입자나 첫 배치 전. 오류가 아니다.
		save(1, (short) 1, RecommendationType.INTEREST_BASED, upcoming);

		RecommendationBoardResponse response = boardService.getBoard(USER_ID);

		assertThat(response.items()).isEmpty();
		assertThat(response.cycle()).isNull();
		assertThat(response.availableAt()).isNull();
	}

	@Test
	void Event_표시_정보를_채워_준다() {
		save(1, (short) 1, RecommendationType.INTEREST_BASED, opened);

		RecommendationBoardResponse.Item item = boardService.getBoard(USER_ID).items().get(0);

		assertThat(item.label()).isEqualTo("기준금리 동결 1");
		assertThat(item.topicCode()).isEqualTo(TopicCode.ECONOMY);
		assertThat(item.eventId()).isEqualTo(eventId(1));
		assertThat(item.score()).isEqualByComparingTo("0.920000");
		assertThat(item.recommendationType()).isEqualTo(RecommendationType.INTEREST_BASED);
		assertThat(item.reason()).isEqualTo("관심 Story 에서 아직 접하지 않은 사건입니다.");
		assertThat(item.userRecommendationId()).isPositive();
	}

	@Test
	void 한_회차를_나누지_않고_전부_돌려준다() {
		// 사용자당 최대 개수가 정해져 있어 한 화면에 들어간다.
		save(1, (short) 1, RecommendationType.INTEREST_BASED, opened);
		save(2, (short) 2, RecommendationType.INTEREST_BASED, opened);
		save(3, (short) 3, RecommendationType.INTEREST_BASED, opened);

		assertThat(boardService.getBoard(USER_ID).items()).hasSize(3);
	}

	@Test
	void 같은_순위가_겹쳐도_빠짐없이_돌려준다() {
		// rank 는 유형 안에서만 유일하다. 두 유형이 한 회차에 들어오면 1위가 둘이다.
		save(1, (short) 1, RecommendationType.INTEREST_BASED, opened);
		save(2, (short) 1, RecommendationType.KNOWLEDGE_GAP, opened);

		assertThat(boardService.getBoard(USER_ID).items()).hasSize(2);
	}


	@Test
	void 응답_시각에는_KST_오프셋이_붙는다() {
		// DB DATETIME(6) 은 KST 벽시계로 저장된다.
		save(1, (short) 1, RecommendationType.INTEREST_BASED, opened);

		RecommendationBoardResponse response = boardService.getBoard(USER_ID);

		assertThat(response.availableAt().getOffset().getTotalSeconds()).isEqualTo(9 * 3600);
	}
}

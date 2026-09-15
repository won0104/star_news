package com.starlightnews.backend.domain.recommendation.service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationCycleWindow;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationEvent;
import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse.Item;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse.UserResult;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationEventRepository;
import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import com.starlightnews.backend.global.enums.RecommendationType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.support.TestFixtures;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
@Transactional
class RecommendationStoreServiceTest {

	private static final String EVENT_ID = "00000128-2001-4000-8000-000000000001";
	private static final String OTHER_EVENT_ID = "00000128-2002-4000-8000-000000000002";

	private static final LocalDateTime MORNING_RUN = LocalDateTime.of(2026, 9, 15, 5, 30);
	private static final LocalDateTime AVAILABLE_AT = LocalDateTime.of(2026, 9, 15, 6, 0);

	private final RecommendationCycleWindow window = RecommendationCycleWindow.from(MORNING_RUN);

	@Autowired
	private RecommendationStoreService storeService;

	@Autowired
	private UserRecommendationRepository userRecommendationRepository;

	@Autowired
	private RecommendationEventRepository eventRepository;

	@Autowired
	private EntityManager entityManager;

	@BeforeEach
	void insertUsers() {
		entityManager.createNativeQuery("INSERT INTO users (user_id, login_id, password_hash, nickname) "
						+ "VALUES (1, 'store-1', 'hashed', '사용자1'), (2, 'store-2', 'hashed', '사용자2')")
				.executeUpdate();
		entityManager.flush();
	}

	private Item item(String eventId, int rank, String type) {
		return new Item(eventId, "기준금리 동결", "ECONOMY",
				new BigDecimal("0.920000"), (short) rank, type, "관심 Story 에서 아직 접하지 않은 사건입니다.");
	}

	private List<UserRecommendation> storedFor(long userId) {
		entityManager.flush();
		entityManager.clear();
		return userRecommendationRepository.findByUserIdAndAvailableAtOrderByRankAsc(userId, AVAILABLE_AT);
	}

	@Test
	void 추천을_회차_정보와_함께_저장한다() {
		storeService.store(List.of(new UserResult(1L, List.of(item(EVENT_ID, 1, "KNOWLEDGE_GAP")))), window);

		assertThat(storedFor(1L)).singleElement().satisfies(saved -> {
			assertThat(saved.getEventId()).isEqualTo(EVENT_ID);
			assertThat(saved.getRecommendationType()).isEqualTo(RecommendationType.KNOWLEDGE_GAP);
			assertThat(saved.getRank()).isEqualTo((short) 1);
			assertThat(saved.getCycle()).isEqualTo(RecommendationCycle.AM);
			assertThat(saved.getRecommendedAt()).isEqualTo(MORNING_RUN);
			assertThat(saved.getAvailableAt()).isEqualTo(AVAILABLE_AT);
		});
	}

	@Test
	void Event_표시_정보도_함께_저장한다() {
		storeService.store(List.of(new UserResult(1L, List.of(item(EVENT_ID, 1, "KNOWLEDGE_GAP")))), window);
		entityManager.flush();
		entityManager.clear();

		RecommendationEvent event = eventRepository.findById(EVENT_ID).orElseThrow();
		assertThat(event.getTitle()).isEqualTo("기준금리 동결");
		assertThat(event.getTopicCode()).isEqualTo(TopicCode.ECONOMY);
	}

	@Test
	void 같은_회차를_다시_저장하면_이전_것을_갈아끼운다() {
		// 재시도해도 결과가 같아야 한다.
		storeService.store(List.of(new UserResult(1L, List.of(item(EVENT_ID, 1, "KNOWLEDGE_GAP")))), window);
		entityManager.flush();

		storeService.store(List.of(new UserResult(1L, List.of(item(OTHER_EVENT_ID, 1, "KNOWLEDGE_GAP")))), window);

		assertThat(storedFor(1L)).extracting(UserRecommendation::getEventId)
				.containsExactly(OTHER_EVENT_ID);
	}

	@Test
	void 회차를_갈아끼울_때_유형을_가리지_않는다() {
		// 유형별로 지우면 한 유형만 새 회차가 되고 다른 유형은 이전 회차가 남는다.
		storeService.store(List.of(new UserResult(1L, List.of(
				item(EVENT_ID, 1, "KNOWLEDGE_GAP"),
				item(OTHER_EVENT_ID, 1, "INTEREST_BASED")))), window);
		entityManager.flush();

		storeService.store(List.of(new UserResult(1L, List.of(item(EVENT_ID, 1, "KNOWLEDGE_GAP")))), window);

		assertThat(storedFor(1L)).hasSize(1);
	}

	@Test
	void 다른_사용자의_회차는_건드리지_않는다() {
		storeService.store(List.of(new UserResult(2L, List.of(item(EVENT_ID, 1, "KNOWLEDGE_GAP")))), window);
		entityManager.flush();

		storeService.store(List.of(new UserResult(1L, List.of(item(EVENT_ID, 1, "KNOWLEDGE_GAP")))), window);

		assertThat(storedFor(2L)).hasSize(1);
	}

	@Test
	void 모르는_추천_유형은_건너뛰고_나머지는_저장한다() {
		// FastAPI 가 새 유형을 추가해도 묶음 전체가 실패하면 안 된다.
		RecommendationStoreResult result = storeService.store(List.of(new UserResult(1L, List.of(
				item(EVENT_ID, 1, "KNOWLEDGE_GAP"),
				item(OTHER_EVENT_ID, 2, "SOMETHING_NEW")))), window);

		assertThat(result.storedItems()).isEqualTo(1);
		assertThat(result.skippedItems()).isEqualTo(1);
		assertThat(storedFor(1L)).extracting(UserRecommendation::getEventId).containsExactly(EVENT_ID);
	}

	@Test
	void 모르는_Topic도_건너뛴다() {
		Item unknownTopic = new Item(EVENT_ID, "제목", "NOT_A_TOPIC",
				new BigDecimal("0.5"), (short) 1, "KNOWLEDGE_GAP", "이유");

		RecommendationStoreResult result =
				storeService.store(List.of(new UserResult(1L, List.of(unknownTopic))), window);

		assertThat(result.skippedItems()).isEqualTo(1);
		assertThat(storedFor(1L)).isEmpty();
	}

	@Test
	void 값이_빠진_추천은_건너뛴다() {
		Item missingRank = new Item(EVENT_ID, "제목", "ECONOMY",
				new BigDecimal("0.5"), null, "KNOWLEDGE_GAP", "이유");

		assertThat(storeService.store(List.of(new UserResult(1L, List.of(missingRank))), window)
				.skippedItems()).isEqualTo(1);
	}

	@Test
	void 같은_순위가_두_번_오면_뒤엣것을_건너뛴다() {
		// 유니크 제약에 걸려 묶음 전체가 실패하는 것을 막는다.
		RecommendationStoreResult result = storeService.store(List.of(new UserResult(1L, List.of(
				item(EVENT_ID, 1, "KNOWLEDGE_GAP"),
				item(OTHER_EVENT_ID, 1, "KNOWLEDGE_GAP")))), window);

		assertThat(result.storedItems()).isEqualTo(1);
		assertThat(result.skippedItems()).isEqualTo(1);
	}

	@Test
	void 같은_Event가_두_번_오면_뒤엣것을_건너뛴다() {
		RecommendationStoreResult result = storeService.store(List.of(new UserResult(1L, List.of(
				item(EVENT_ID, 1, "KNOWLEDGE_GAP"),
				item(EVENT_ID, 2, "KNOWLEDGE_GAP")))), window);

		assertThat(result.storedItems()).isEqualTo(1);
		assertThat(result.skippedItems()).isEqualTo(1);
	}

	@Test
	void 유형이_다르면_같은_순위를_그대로_저장한다() {
		RecommendationStoreResult result = storeService.store(List.of(new UserResult(1L, List.of(
				item(EVENT_ID, 1, "KNOWLEDGE_GAP"),
				item(OTHER_EVENT_ID, 1, "INTEREST_BASED")))), window);

		assertThat(result.storedItems()).isEqualTo(2);
		assertThat(storedFor(1L)).hasSize(2);
	}

	@Test
	void 추천이_하나도_없는_사용자는_저장_사용자에서_빠진다() {
		RecommendationStoreResult result =
				storeService.store(List.of(new UserResult(1L, List.of())), window);

		assertThat(result.storedUsers()).isZero();
		assertThat(result.storedItems()).isZero();
	}

	@Test
	void 빈_결과면_아무것도_하지_않는다() {
		assertThat(storeService.store(List.of(), window)).isEqualTo(RecommendationStoreResult.empty());
	}

	@Test
	void 여러_사용자를_한_번에_저장한다() {
		RecommendationStoreResult result = storeService.store(List.of(
				new UserResult(1L, List.of(item(EVENT_ID, 1, "KNOWLEDGE_GAP"))),
				new UserResult(2L, List.of(item(EVENT_ID, 1, "INTEREST_BASED")))), window);

		assertThat(result.storedUsers()).isEqualTo(2);
		assertThat(result.storedItems()).isEqualTo(2);
	}
}

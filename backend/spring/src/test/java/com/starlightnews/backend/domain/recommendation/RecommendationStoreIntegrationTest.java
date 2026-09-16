package com.starlightnews.backend.domain.recommendation;

import java.time.LocalDateTime;
import java.util.List;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationCycleWindow;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationEvent;
import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationCalculateResponse;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationEventRepository;
import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import com.starlightnews.backend.domain.recommendation.service.RecommendationRetentionService;
import com.starlightnews.backend.domain.recommendation.service.RecommendationStoreResult;
import com.starlightnews.backend.domain.recommendation.service.RecommendationStoreService;
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
 * FastAPI 가 보낸 JSON 이 실제 MySQL 저장까지 이어지는지 확인한다.
 *
 * <p>조각별 테스트는 자바 객체를 직접 만들어 넣으므로 필드 이름이 어긋나도 드러나지 않는다.
 * 여기서는 명세에 적힌 본문을 그대로 역직렬화해서, 이름이 하나라도 다르면 값이 비어 실패하게 한다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class RecommendationStoreIntegrationTest {

	private static final String EVENT_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301";

	private static final LocalDateTime MORNING_RUN = LocalDateTime.of(2026, 9, 15, 5, 30);
	private static final LocalDateTime AVAILABLE_AT = LocalDateTime.of(2026, 9, 15, 6, 0);

	/** 노션 명세의 Response 예시 그대로. */
	private static final String SPEC_RESPONSE = """
			{
			  "data": {
			    "cycle": "AM",
			    "results": [
			      {
			        "userId": 1,
			        "items": [
			          {
			            "eventId": "%s",
			            "label": "한국은행 기준금리 동결",
			            "topicCode": "ECONOMY",
			            "score": 0.92,
			            "rank": 1,
			            "recommendationType": "KNOWLEDGE_GAP",
			            "reason": "관심 있는 통화정책 Story에서 아직 접하지 않은 사건입니다."
			          }
			        ]
			      }
			    ]
			  }
			}
			""".formatted(EVENT_ID);

	@Autowired
	private RecommendationStoreService storeService;

	@Autowired
	private RecommendationRetentionService retentionService;

	@Autowired
	private UserRecommendationRepository userRecommendationRepository;

	@Autowired
	private RecommendationEventRepository eventRepository;

	@Autowired
	private ObjectMapper objectMapper;

	@Autowired
	private EntityManager entityManager;

	@BeforeEach
	void insertUser() {
		entityManager.createNativeQuery("INSERT INTO users (user_id, login_id, password_hash, nickname) "
						+ "VALUES (1, 'rec-integration', 'hashed', '통합테스트')")
				.executeUpdate();
		entityManager.flush();
	}

	private RecommendationCalculateResponse parse(String json) throws Exception {
		return objectMapper.readValue(json, RecommendationCalculateResponse.class);
	}

	private List<UserRecommendation> stored() {
		entityManager.flush();
		entityManager.clear();
		return userRecommendationRepository.findByUserIdAndAvailableAtOrderByRankAsc(1L, AVAILABLE_AT);
	}

	@Test
	void 명세의_응답_본문을_그대로_저장한다() throws Exception {
		var response = parse(SPEC_RESPONSE);

		storeService.store(response.results(), RecommendationCycleWindow.from(MORNING_RUN));

		assertThat(stored()).singleElement().satisfies(saved -> {
			assertThat(saved.getUserId()).isEqualTo(1L);
			assertThat(saved.getEventId()).isEqualTo(EVENT_ID);
			assertThat(saved.getRecommendationType()).isEqualTo(RecommendationType.KNOWLEDGE_GAP);
			assertThat(saved.getRecommendationScore()).isEqualByComparingTo("0.92");
			assertThat(saved.getRank()).isEqualTo((short) 1);
			assertThat(saved.getReason()).isEqualTo("관심 있는 통화정책 Story에서 아직 접하지 않은 사건입니다.");
			assertThat(saved.getCycle()).isEqualTo(RecommendationCycle.AM);
			assertThat(saved.getAvailableAt()).isEqualTo(AVAILABLE_AT);
		});
	}

	@Test
	void Event_표시_정보도_함께_저장된다() throws Exception {
		storeService.store(parse(SPEC_RESPONSE).results(), RecommendationCycleWindow.from(MORNING_RUN));
		entityManager.flush();
		entityManager.clear();

		RecommendationEvent event = eventRepository.findById(EVENT_ID).orElseThrow();
		assertThat(event.getTitle()).isEqualTo("한국은행 기준금리 동결");
		assertThat(event.getTopicCode()).isEqualTo(TopicCode.ECONOMY);
		// 요약은 이 단계에서 만들지 않는다. 상세 조회 때 만들어 재사용한다.
		assertThat(event.getSummary()).isNull();
		assertThat(event.getSummaryStatus()).isEqualTo("NOT_REQUESTED");
	}

	@Test
	void FastAPI가_필드를_추가해도_깨지지_않는다() throws Exception {
		// 명세보다 앞서 구현이 나가는 일이 있었다. 모르는 필드 때문에 회차가 통째로 실패하면 안 된다.
		String withExtraField = SPEC_RESPONSE.replace(
				"\"rank\": 1,", "\"rank\": 1,\n            \"someNewField\": \"value\",");

		var response = parse(withExtraField);

		assertThat(response.results()).hasSize(1);
		storeService.store(response.results(), RecommendationCycleWindow.from(MORNING_RUN));
		assertThat(stored()).hasSize(1);
	}

	@Test
	void data가_없는_응답도_처리한다() throws Exception {
		var response = parse("{}");

		assertThat(response.results()).isEmpty();
		assertThat(storeService.store(response.results(), RecommendationCycleWindow.from(MORNING_RUN)))
				.isEqualTo(RecommendationStoreResult.empty());
	}

	@Test
	void 회차를_다시_계산해_저장하면_이전_회차를_갈아끼운다() throws Exception {
		storeService.store(parse(SPEC_RESPONSE).results(), RecommendationCycleWindow.from(MORNING_RUN));
		entityManager.flush();

		// 같은 회차를 47분 뒤에 재시도해도 공개 시각이 같아 같은 회차로 덮인다.
		storeService.store(parse(SPEC_RESPONSE).results(),
				RecommendationCycleWindow.from(MORNING_RUN.plusMinutes(17)));

		assertThat(stored()).hasSize(1);
	}

	@Test
	void 오후_회차는_18시에_공개된다() throws Exception {
		storeService.store(parse(SPEC_RESPONSE).results(),
				RecommendationCycleWindow.from(LocalDateTime.of(2026, 9, 15, 17, 30)));
		entityManager.flush();
		entityManager.clear();

		assertThat(userRecommendationRepository.findByUserIdAndAvailableAtOrderByRankAsc(
				1L, LocalDateTime.of(2026, 9, 15, 18, 0)))
				.singleElement()
				.satisfies(saved -> assertThat(saved.getCycle()).isEqualTo(RecommendationCycle.PM));
	}

	@Test
	void 응답의_회차가_요청과_같으면_그대로_저장한다() throws Exception {
		// 응답 예시의 cycle 은 AM 이고 05:30 계산도 AM 이라 어긋나지 않는다.
		storeService.store(parse(SPEC_RESPONSE), RecommendationCycleWindow.from(MORNING_RUN));

		assertThat(stored()).singleElement()
				.satisfies(saved -> assertThat(saved.getCycle()).isEqualTo(RecommendationCycle.AM));
	}

	@Test
	void 응답의_회차가_달라도_요청_기준으로_저장한다() throws Exception {
		// 회차는 우리 계산 시각이 정한다. 어긋나면 경고만 남기고 저장은 계속한다.
		String pmResponse = SPEC_RESPONSE.replace("\"cycle\": \"AM\"", "\"cycle\": \"PM\"");

		storeService.store(parse(pmResponse), RecommendationCycleWindow.from(MORNING_RUN));

		assertThat(stored()).singleElement()
				.satisfies(saved -> assertThat(saved.getCycle()).isEqualTo(RecommendationCycle.AM));
	}

	@Test
	void 보관_기간이_지난_회차는_정리되고_이번_회차는_남는다() throws Exception {
		storeService.store(parse(SPEC_RESPONSE).results(),
				RecommendationCycleWindow.from(MORNING_RUN.minusDays(10)));
		storeService.store(parse(SPEC_RESPONSE).results(), RecommendationCycleWindow.from(MORNING_RUN));
		entityManager.flush();

		assertThat(retentionService.purgeExpired(MORNING_RUN)).isEqualTo(1);

		assertThat(stored()).hasSize(1);
		// Event 표시 정보는 남는다. 요약을 재사용해야 하기 때문이다.
		entityManager.clear();
		assertThat(eventRepository.findById(EVENT_ID)).isPresent();
	}
}

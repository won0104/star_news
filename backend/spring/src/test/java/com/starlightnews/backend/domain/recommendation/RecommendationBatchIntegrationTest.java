package com.starlightnews.backend.domain.recommendation;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationRun;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunChunk;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunChunkStatus;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunStatus;
import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationRunChunkRepository;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationRunRepository;
import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import com.starlightnews.backend.domain.recommendation.service.RecommendationBatchResult;
import com.starlightnews.backend.domain.recommendation.service.EventSummaryService;
import com.starlightnews.backend.domain.recommendation.service.RecommendationBatchService;
import com.starlightnews.backend.global.client.FastApiClient;
import com.starlightnews.backend.global.client.FastApiProperties;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

/**
 * 사용자 조회부터 MySQL 저장까지 한 회차를 통째로 확인한다.
 *
 * <p>FastAPI 만 {@link MockRestServiceServer} 로 세우고 나머지는 실물을 쓴다. 조각별 테스트는
 * 클라이언트를 목으로 막아서 <b>실제로 어떤 JSON 이 나가는지</b>는 드러나지 않는다. 필드 이름이
 * 어긋나 요청이 거절되는 일을 이미 두 번 겪어, 여기서는 나가는 본문을 직접 본다.
 */
@SpringBootTest(properties = {
		"spring.main.allow-bean-definition-overriding=true",
		// 키가 없으면 FastApiClient 가 호출 전에 끊는다. 테스트 환경에는 실제 키가 없다.
		"app.fastapi.api-key=test-internal-key",
		"app.recommendation.chunk-size=1",
		"app.recommendation.limit-per-user=10"
})
@ActiveProfiles("test")
@Transactional
@Import(RecommendationBatchIntegrationTest.MockFastApiConfig.class)
class RecommendationBatchIntegrationTest {

	/**
	 * 요약 생성은 여기서 보지 않는다. 이 테스트는 배치가 FastAPI 와 주고받는 내용을 확인하는 것이고,
	 * 요약은 Neo4j 와 GMS 를 타므로 {@code EventSummaryServiceTest} 가 따로 본다.
	 */
	@MockitoBean
	private EventSummaryService eventSummaryService;

	private static final String CALCULATE_URL = "/internal/v1/recommendations/calculate";
	private static final String EVENT_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301";

	private static final LocalDateTime MORNING_RUN = LocalDateTime.of(2026, 9, 15, 5, 30);
	private static final LocalDateTime AVAILABLE_AT = LocalDateTime.of(2026, 9, 15, 6, 0);

	/**
	 * {@code fastApiRestClient} 를 MockRestServiceServer 에 묶인 것으로 바꾼다.
	 *
	 * <p>운영 빈은 {@code HttpClients.create} 가 requestFactory 를 지정해 만들어서, 주입된 Builder 에
	 * 서버를 걸어도 그 설정이 덮어써진다. 그래서 빈 자체를 갈아끼운다.
	 */
	@TestConfiguration(proxyBeanMethods = false)
	static class MockFastApiConfig {

		private final RestClient.Builder builder = RestClient.builder();

		@Bean
		MockRestServiceServer fastApiMockServer() {
			return MockRestServiceServer.bindTo(builder).ignoreExpectOrder(true).build();
		}

		/** 서버 빈을 인자로 받아 반드시 먼저 만들어지게 한다. 순서가 뒤집히면 가로채기가 안 걸린다. */
		@Bean
		RestClient fastApiRestClient(MockRestServiceServer fastApiMockServer, FastApiProperties properties) {
			return builder.baseUrl(properties.baseUrl()).build();
		}
	}

	@Autowired
	private RecommendationBatchService batchService;

	@Autowired
	private UserRecommendationRepository userRecommendationRepository;

	@Autowired
	private MockRestServiceServer fastApiMockServer;

	@Autowired
	private RecommendationRunRepository runRepository;

	@Autowired
	private RecommendationRunChunkRepository chunkRepository;

	@Autowired
	private FastApiProperties fastApiProperties;

	@Autowired
	private EntityManager entityManager;

	@BeforeEach
	void seed() {
		fastApiMockServer.reset();
		entityManager.createNativeQuery("INSERT INTO users (user_id, login_id, password_hash, nickname) "
						+ "VALUES (1, 'batch-1', 'hashed', '사용자1'), (2, 'batch-2', 'hashed', '사용자2')")
				.executeUpdate();
		entityManager.flush();
	}

	private String responseFor(long userId) {
		return """
				{"data": {"cycle": "AM", "results": [
				  {"userId": %d, "items": [
				    {"eventId": "%s", "label": "한국은행 기준금리 동결", "topicCode": "ECONOMY",
				     "score": 0.92, "rank": 1, "recommendationType": "COLD_START"}
				  ]}
				]}}
				""".formatted(userId, EVENT_ID);
	}

	private void expectCalculate(String responseBody) {
		fastApiMockServer.expect(requestTo(fastApiProperties.baseUrl() + CALCULATE_URL))
				.andExpect(method(HttpMethod.POST))
				.andRespond(withSuccess(responseBody, MediaType.APPLICATION_JSON));
	}

	private List<UserRecommendation> storedFor(long userId) {
		entityManager.flush();
		entityManager.clear();
		return userRecommendationRepository.findByUserIdAndAvailableAtOrderByRankAsc(userId, AVAILABLE_AT);
	}

	@Test
	void 명세와_같은_요청_본문을_보낸다() {
		// 이름이 하나라도 다르면 FastAPI 가 거절한다.
		fastApiMockServer.expect(requestTo(fastApiProperties.baseUrl() + CALCULATE_URL))
				.andExpect(method(HttpMethod.POST))
				.andExpect(header(FastApiClient.INTERNAL_API_KEY_HEADER, fastApiProperties.apiKey()))
				.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
				.andExpect(jsonPath("$.cycle").value("AM"))
				.andExpect(jsonPath("$.users[0].userId").value(1))
				.andExpect(jsonPath("$.users[0].limit").value(10))
				.andRespond(withSuccess(responseFor(1L), MediaType.APPLICATION_JSON));
		expectCalculate(responseFor(2L));

		batchService.generate(MORNING_RUN);

		fastApiMockServer.verify();
	}

	@Test
	void 계산_결과가_MySQL에_저장된다() {
		expectCalculate(responseFor(1L));
		expectCalculate(responseFor(2L));

		RecommendationBatchResult result = batchService.generate(MORNING_RUN);

		assertThat(result.storedUsers()).isEqualTo(2);
		assertThat(storedFor(1L)).singleElement().satisfies(saved -> {
			assertThat(saved.getEventId()).isEqualTo(EVENT_ID);
			assertThat(saved.getCycle()).isEqualTo(RecommendationCycle.AM);
			assertThat(saved.getAvailableAt()).isEqualTo(AVAILABLE_AT);
		});
	}

	@Test
	void 묶음이_나뉘어도_같은_회차로_저장된다() {
		// 묶음마다 회차 시각을 새로 정하면 한 회차가 여러 개로 쪼개진다.
		expectCalculate(responseFor(1L));
		expectCalculate(responseFor(2L));

		batchService.generate(MORNING_RUN);

		assertThat(storedFor(1L)).hasSize(1);
		assertThat(storedFor(2L)).hasSize(1);
	}

	@Test
	void 한_묶음이_실패해도_다른_묶음은_저장된다() {
		fastApiMockServer.expect(requestTo(fastApiProperties.baseUrl() + CALCULATE_URL))
				.andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));
		expectCalculate(responseFor(2L));

		RecommendationBatchResult result = batchService.generate(MORNING_RUN);

		assertThat(result.failedUsers()).isEqualTo(1);
		assertThat(result.storedUsers()).isEqualTo(1);
	}

	@Test
	void User_Graph가_없어_404여도_회차는_계속된다() {
		// 신규 가입자가 섞이면 생긴다. 회차 전체를 멈출 이유가 없다.
		fastApiMockServer.expect(requestTo(fastApiProperties.baseUrl() + CALCULATE_URL))
				.andRespond(withStatus(HttpStatus.NOT_FOUND)
						.body("{\"code\":\"USER_RECOMMENDATION_CONTEXT_NOT_FOUND\",\"message\":\"없음\"}")
						.contentType(MediaType.APPLICATION_JSON));
		expectCalculate(responseFor(2L));

		RecommendationBatchResult result = batchService.generate(MORNING_RUN);

		assertThat(result.failedUsers()).isEqualTo(1);
		assertThat(storedFor(2L)).hasSize(1);
	}

	@Test
	void 오후_회차는_PM으로_요청하고_18시에_공개된다() {
		fastApiMockServer.expect(requestTo(fastApiProperties.baseUrl() + CALCULATE_URL))
				.andExpect(jsonPath("$.cycle").value("PM"))
				.andRespond(withSuccess(responseFor(1L).replace("\"AM\"", "\"PM\""),
						MediaType.APPLICATION_JSON));
		expectCalculate(responseFor(2L).replace("\"AM\"", "\"PM\""));

		batchService.generate(LocalDateTime.of(2026, 9, 15, 17, 30));
		entityManager.flush();
		entityManager.clear();

		assertThat(userRecommendationRepository.findByUserIdAndAvailableAtOrderByRankAsc(
				1L, LocalDateTime.of(2026, 9, 15, 18, 0))).hasSize(1);
	}

	// --- 실행 기록 ---

	private RecommendationRun latestRun() {
		entityManager.flush();
		entityManager.clear();
		return runRepository.findAll().stream()
				.filter(run -> run.getAvailableAt().equals(AVAILABLE_AT))
				.reduce((first, second) -> second)
				.orElseThrow();
	}

	@Test
	void 모든_묶음이_성공하면_완료로_기록된다() {
		expectCalculate(responseFor(1L));
		expectCalculate(responseFor(2L));

		batchService.generate(MORNING_RUN);

		RecommendationRun run = latestRun();
		assertThat(run.getStatus()).isEqualTo(RecommendationRunStatus.COMPLETED);
		assertThat(run.getCycle()).isEqualTo(RecommendationCycle.AM);
		assertThat(run.getStartedAt()).isEqualTo(MORNING_RUN);
		assertThat(run.getFinishedAt()).isNotNull();
		assertThat(run.getTotalChunks()).isEqualTo(2);
		assertThat(run.getTargetUsers()).isEqualTo(2);
		assertThat(run.getStoredUsers()).isEqualTo(2);
	}

	@Test
	void 실패한_묶음은_사용자와_원인이_남고_회차는_부분_완료다() {
		// 묶음 크기 1이라 사용자 1 묶음이 실패, 사용자 2 묶음이 성공한다.
		fastApiMockServer.expect(requestTo(fastApiProperties.baseUrl() + CALCULATE_URL))
				.andExpect(jsonPath("$.users[0].userId").value(1))
				.andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));
		expectCalculate(responseFor(2L));

		batchService.generate(MORNING_RUN);

		RecommendationRun run = latestRun();
		assertThat(run.getStatus()).isEqualTo(RecommendationRunStatus.PARTIAL);
		assertThat(run.getFailedChunks()).isEqualTo(1);
		assertThat(run.getFailedUsers()).isEqualTo(1);

		List<RecommendationRunChunk> chunks = chunkRepository.findByRunIdOrderByChunkNoAsc(run.getRunId());
		assertThat(chunks).hasSize(2);
		assertThat(chunks.get(0).getStatus()).isEqualTo(RecommendationRunChunkStatus.FAILED);
		assertThat(chunks.get(0).getUserIds()).containsExactly(1L);
		assertThat(chunks.get(0).getFailureCode()).isEqualTo("INTERNAL_API_UNAVAILABLE");
		assertThat(chunks.get(1).getStatus()).isEqualTo(RecommendationRunChunkStatus.SUCCEEDED);
		assertThat(chunks.get(1).getFailureCode()).isNull();
	}

	@Test
	void 모든_묶음이_실패하면_실패로_기록된다() {
		fastApiMockServer.expect(requestTo(fastApiProperties.baseUrl() + CALCULATE_URL))
				.andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));
		fastApiMockServer.expect(requestTo(fastApiProperties.baseUrl() + CALCULATE_URL))
				.andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));

		batchService.generate(MORNING_RUN);

		assertThat(latestRun().getStatus()).isEqualTo(RecommendationRunStatus.FAILED);
	}
}

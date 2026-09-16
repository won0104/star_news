package com.starlightnews.backend.domain.recommendation.service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.domain.recommendation.repository.EventArticleRepository;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationEventRepository;
import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import com.starlightnews.backend.global.client.GmsClient;
import com.starlightnews.backend.global.client.GmsErrorCode;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import com.starlightnews.backend.global.enums.RecommendationType;
import com.starlightnews.backend.global.error.BusinessException;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * 추천 Event 요약 생성.
 *
 * <p>GMS 와 Neo4j 는 대역으로 둔다. 확인할 것은 "어떤 Event 를 고르고 결과를 어떻게 남기는가" 다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class EventSummaryServiceTest {

	private static final long USER_ID = 94_100L;
	private static final long ORGANIZATION_ID = 94_900L;
	private static final String EVENT_ID = "00000020-0920-4000-8000-000000000001";
	private static final String OTHER_EVENT_ID = "00000020-0920-4000-8000-000000000002";

	@Autowired
	private EventSummaryService summaryService;

	@Autowired
	private RecommendationEventRepository eventRepository;

	@Autowired
	private UserRecommendationRepository userRecommendationRepository;

	@Autowired
	private EntityManager entityManager;

	@MockitoBean
	private GmsClient gmsClient;

	@MockitoBean
	private EventArticleRepository eventArticleRepository;

	private long articleId;
	private LocalDateTime availableAt;

	@BeforeEach
	void insertFixtures() {
		availableAt = LocalDateTime.now(ZoneId.of("Asia/Seoul")).minusHours(2).withNano(0);

		entityManager.createNativeQuery("INSERT INTO users (user_id, login_id, password_hash, nickname) "
						+ "VALUES (?1, 'summary-user', 'hashed-password', '요약사용자') "
						+ "ON DUPLICATE KEY UPDATE user_id = user_id")
				.setParameter(1, USER_ID).executeUpdate();
		entityManager.createNativeQuery("INSERT INTO news_organizations (organization_id, name, domain) "
						+ "VALUES (?1, '연합뉴스', 'yna.co.kr') "
						+ "ON DUPLICATE KEY UPDATE organization_id = organization_id")
				.setParameter(1, ORGANIZATION_ID).executeUpdate();
		insertEvent(EVENT_ID, "한국은행 1월 기준금리 동결");
		insertEvent(OTHER_EVENT_ID, "반도체 메가 클러스터 조성");
		entityManager.flush();

		articleId = insertArticle();
		given(eventArticleRepository.findArticleIdsByEvent(anyString())).willReturn(List.of(articleId));
		given(gmsClient.generate(anyString(), anyString())).willReturn("금통위가 기준금리를 동결했다.");
	}

	private void insertEvent(String eventId, String title) {
		entityManager.createNativeQuery("INSERT INTO recommendation_events "
						+ "(event_id, title, topic_code, summary_status) "
						+ "VALUES (?1, ?2, 'ECONOMY', 'NOT_REQUESTED') "
						+ "ON DUPLICATE KEY UPDATE title = ?2, summary = NULL, "
						+ "summary_status = 'NOT_REQUESTED', summary_generated_at = NULL, "
						+ "event_updated_at = NULL")
				.setParameter(1, eventId).setParameter(2, title).executeUpdate();
	}

	private long insertArticle() {
		String url = "https://yna.co.kr/summary-source";
		entityManager.createNativeQuery("INSERT INTO articles "
						+ "(organization_id, title, url, url_hash, published_at, content, content_type, "
						+ " analysis_status) "
						+ "VALUES (?1, '한국은행 기준금리 동결', ?2, UNHEX(SHA2(?2, 256)), "
						+ " '2026-09-14 09:00:00', ?3, 'FULL_TEXT', 'COMPLETED') "
						+ "ON DUPLICATE KEY UPDATE title = title")
				.setParameter(1, ORGANIZATION_ID).setParameter(2, url)
				.setParameter(3, "금통위가 기준금리를 연 3.50%로 동결했다. ".repeat(20)).executeUpdate();
		entityManager.flush();
		return ((Number) entityManager.createNativeQuery("SELECT article_id FROM articles WHERE url = ?1")
				.setParameter(1, url).getSingleResult()).longValue();
	}

	private void recommend(String eventId, short rank) {
		userRecommendationRepository.save(new UserRecommendation(USER_ID, eventId,
				RecommendationType.INTEREST_BASED, new BigDecimal("0.920000"), rank, "근거",
				availableAt.minusMinutes(30), RecommendationCycle.PM, availableAt));
		entityManager.flush();
	}

	private Object[] eventRow(String eventId) {
		entityManager.flush();
		entityManager.clear();
		return (Object[]) entityManager.createNativeQuery(
						"SELECT summary, summary_status, summary_generated_at "
								+ "FROM recommendation_events WHERE event_id = ?1")
				.setParameter(1, eventId).getSingleResult();
	}

	@Test
	void 요약이_없는_Event_의_요약을_만들어_저장한다() {
		summaryService.generateFor(List.of(EVENT_ID));

		Object[] row = eventRow(EVENT_ID);
		assertThat(row[0]).isEqualTo("금통위가 기준금리를 동결했다.");
		assertThat(row[1]).isEqualTo("COMPLETED");
		assertThat(row[2]).isNotNull();
	}

	@Test
	void 이미_요약이_있으면_다시_만들지_않는다() {
		entityManager.createNativeQuery("UPDATE recommendation_events SET summary = '기존 요약', "
						+ "summary_status = 'COMPLETED', summary_generated_at = NOW(6) WHERE event_id = ?1")
				.setParameter(1, EVENT_ID).executeUpdate();
		entityManager.flush();

		assertThat(summaryService.generateFor(List.of(EVENT_ID))).isZero();
		verify(gmsClient, never()).generate(anyString(), anyString());
	}

	@Test
	void Event_제목이_바뀌었으면_다시_만든다() {
		// event_updated_at 이 요약 생성 시각보다 뒤면 내용이 바뀐 것이다.
		entityManager.createNativeQuery("UPDATE recommendation_events SET summary = '오래된 요약', "
						+ "summary_status = 'COMPLETED', summary_generated_at = ?2, event_updated_at = ?3 "
						+ "WHERE event_id = ?1")
				.setParameter(1, EVENT_ID)
				.setParameter(2, LocalDateTime.now().minusDays(1))
				.setParameter(3, LocalDateTime.now())
				.executeUpdate();
		entityManager.flush();

		assertThat(summaryService.generateFor(List.of(EVENT_ID))).isEqualTo(1);
		assertThat(eventRow(EVENT_ID)[0]).isEqualTo("금통위가 기준금리를 동결했다.");
	}

	@Test
	void 지난_회차에_실패한_Event_는_다시_시도한다() {
		entityManager.createNativeQuery("UPDATE recommendation_events SET summary_status = 'FAILED' "
						+ "WHERE event_id = ?1")
				.setParameter(1, EVENT_ID).executeUpdate();
		entityManager.flush();

		assertThat(summaryService.generateFor(List.of(EVENT_ID))).isEqualTo(1);
	}

	@Test
	void 관련도_높은_기사_세_개까지만_넣는다() {
		given(eventArticleRepository.findArticleIdsByEvent(EVENT_ID))
				.willReturn(List.of(articleId, articleId, articleId, articleId, articleId));

		summaryService.generateFor(List.of(EVENT_ID));

		verify(gmsClient).generate(anyString(), anyString());
	}

	@Test
	void 근거_기사가_없으면_건너뛴다() {
		// 기사가 아직 그래프에 붙지 않았다. 빈 내용으로 부르면 헛돈다.
		given(eventArticleRepository.findArticleIdsByEvent(EVENT_ID)).willReturn(List.of());

		assertThat(summaryService.generateFor(List.of(EVENT_ID))).isZero();
		verify(gmsClient, never()).generate(anyString(), anyString());
		assertThat(eventRow(EVENT_ID)[1]).isEqualTo("NOT_REQUESTED");
	}

	@Test
	void 호출에_실패하면_실패로_표시하고_넘어간다() {
		given(gmsClient.generate(anyString(), anyString()))
				.willThrow(new BusinessException(GmsErrorCode.GMS_RATE_LIMITED));

		assertThat(summaryService.generateFor(List.of(EVENT_ID))).isZero();

		Object[] row = eventRow(EVENT_ID);
		assertThat(row[1]).isEqualTo("FAILED");
		assertThat(row[0]).isNull();
	}

	@Test
	void 한_건이_실패해도_나머지는_계속한다() {
		given(gmsClient.generate(anyString(), anyString()))
				.willThrow(new BusinessException(GmsErrorCode.GMS_UNAVAILABLE))
				.willReturn("두 번째 Event 요약이다.");

		assertThat(summaryService.generateFor(List.of(EVENT_ID, OTHER_EVENT_ID))).isEqualTo(1);
	}

	@Test
	void 실패해도_지난_요약은_지우지_않는다() {
		// 빈 화면보다 오래된 요약이라도 보여 주는 편이 낫다.
		entityManager.createNativeQuery("UPDATE recommendation_events SET summary = '지난 회차 요약', "
						+ "summary_status = 'COMPLETED', summary_generated_at = ?2, event_updated_at = ?3 "
						+ "WHERE event_id = ?1")
				.setParameter(1, EVENT_ID)
				.setParameter(2, LocalDateTime.now().minusDays(1))
				.setParameter(3, LocalDateTime.now())
				.executeUpdate();
		entityManager.flush();
		given(gmsClient.generate(anyString(), anyString()))
				.willThrow(new BusinessException(GmsErrorCode.GMS_UNAVAILABLE));

		summaryService.generateFor(List.of(EVENT_ID));

		Object[] row = eventRow(EVENT_ID);
		assertThat(row[0]).isEqualTo("지난 회차 요약");
		assertThat(row[1]).isEqualTo("FAILED");
	}

	@Test
	void 대상이_없으면_부르지_않는다() {
		assertThat(summaryService.generateFor(List.of())).isZero();
		verify(gmsClient, never()).generate(anyString(), anyString());
	}

	@Test
	void 회차에_추천된_Event_만_대상이다() {
		// 쓰이지도 않을 Event 의 요약을 만들면 호출만 늘어난다.
		recommend(EVENT_ID, (short) 1);

		assertThat(summaryService.generateForCycle(availableAt)).isEqualTo(1);
		assertThat(eventRow(OTHER_EVENT_ID)[1]).isEqualTo("NOT_REQUESTED");
	}

	@Test
	void 같은_Event_를_여러_사용자가_받아도_한_번만_만든다() {
		entityManager.createNativeQuery("INSERT INTO users (user_id, login_id, password_hash, nickname) "
						+ "VALUES (?1, 'summary-user-2', 'hashed-password', '요약사용자2') "
						+ "ON DUPLICATE KEY UPDATE user_id = user_id")
				.setParameter(1, USER_ID + 1).executeUpdate();
		recommend(EVENT_ID, (short) 1);
		userRecommendationRepository.save(new UserRecommendation(USER_ID + 1, EVENT_ID,
				RecommendationType.INTEREST_BASED, new BigDecimal("0.910000"), (short) 1, "근거",
				availableAt.minusMinutes(30), RecommendationCycle.PM, availableAt));
		entityManager.flush();

		assertThat(summaryService.generateForCycle(availableAt)).isEqualTo(1);
		verify(gmsClient).generate(anyString(), anyString());
	}
}

package com.starlightnews.backend.domain.recommendation.service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;

import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationDetailResponse;
import com.starlightnews.backend.domain.recommendation.repository.EventArticleRepository;
import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import com.starlightnews.backend.global.enums.RecommendationCycle;
import com.starlightnews.backend.global.enums.RecommendationType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;

/**
 * 추천 Event 상세 조회 서비스.
 *
 * <p>관련 기사는 Neo4j 에서 온다. 그래프는 이 테스트의 관심사가 아니라 대역으로 둔다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class RecommendationDetailServiceTest {

	private static final long USER_ID = 95_100L;
	private static final long OTHER_USER_ID = 95_200L;
	private static final long ORGANIZATION_ID = 95_900L;
	private static final String EVENT_ID = "00000020-0920-4000-8000-000000000001";

	@Autowired
	private RecommendationDetailService detailService;

	@Autowired
	private UserRecommendationRepository userRecommendationRepository;

	@Autowired
	private EntityManager entityManager;

	@MockitoBean
	private EventArticleRepository eventArticleRepository;

	private LocalDateTime availableAt;

	@BeforeEach
	void insertFixtures() {
		availableAt = LocalDateTime.now(ZoneId.of("Asia/Seoul")).minusHours(2).withNano(0);

		for (long userId : new long[] {USER_ID, OTHER_USER_ID}) {
			entityManager.createNativeQuery("INSERT INTO users (user_id, login_id, password_hash, nickname) "
							+ "VALUES (?1, ?2, 'hashed-password', ?3) "
							+ "ON DUPLICATE KEY UPDATE user_id = user_id")
					.setParameter(1, userId).setParameter(2, "detail-user-" + userId)
					.setParameter(3, "상세사용자" + userId).executeUpdate();
		}
		entityManager.createNativeQuery("INSERT INTO recommendation_events "
						+ "(event_id, title, topic_code, summary_status) "
						+ "VALUES (?1, '한국은행 1월 기준금리 동결', 'ECONOMY', 'NOT_REQUESTED') "
						+ "ON DUPLICATE KEY UPDATE summary = NULL, summary_status = 'NOT_REQUESTED'")
				.setParameter(1, EVENT_ID).executeUpdate();
		entityManager.createNativeQuery("INSERT INTO news_organizations (organization_id, name, domain) "
						+ "VALUES (?1, '연합뉴스', 'yna.co.kr') "
						+ "ON DUPLICATE KEY UPDATE organization_id = organization_id")
				.setParameter(1, ORGANIZATION_ID).executeUpdate();
		entityManager.flush();

		given(eventArticleRepository.findArticleIdsByEvent(EVENT_ID)).willReturn(List.of());
	}

	private long insertArticle(String title, String topicCode) {
		String url = "https://yna.co.kr/" + title.hashCode();
		entityManager.createNativeQuery("INSERT INTO articles "
						+ "(organization_id, title, url, url_hash, published_at, content, content_type, "
						+ " analysis_status, topic_code) "
						+ "VALUES (?1, ?2, ?3, UNHEX(SHA2(?3, 256)), '2026-09-14 09:00:00', '본문', "
						+ " 'FULL_TEXT', 'COMPLETED', ?4)")
				.setParameter(1, ORGANIZATION_ID).setParameter(2, title)
				.setParameter(3, url).setParameter(4, topicCode).executeUpdate();
		entityManager.flush();
		return ((Number) entityManager.createNativeQuery("SELECT article_id FROM articles WHERE url = ?1")
				.setParameter(1, url).getSingleResult()).longValue();
	}

	private long saveRecommendation(long userId) {
		UserRecommendation saved = userRecommendationRepository.save(new UserRecommendation(userId,
				EVENT_ID, RecommendationType.NORMAL, new BigDecimal("0.920000"), (short) 1, availableAt.minusMinutes(30),
				RecommendationCycle.PM, availableAt));
		entityManager.flush();
		return saved.getUserRecommendationId();
	}

	@Test
	void Event_정보를_돌려준다() {
		long id = saveRecommendation(USER_ID);

		RecommendationDetailResponse response = detailService.getDetail(USER_ID, id);

		assertThat(response.userRecommendationId()).isEqualTo(id);
		assertThat(response.eventId()).isEqualTo(EVENT_ID);
		assertThat(response.label()).isEqualTo("한국은행 1월 기준금리 동결");
		assertThat(response.topicCode()).isEqualTo(TopicCode.ECONOMY);
	}

	@Test
	void 없는_추천은_404다() {
		assertThatThrownBy(() -> detailService.getDetail(USER_ID, 9_999_999L))
				.isInstanceOf(BusinessException.class)
				.hasFieldOrPropertyWithValue("errorCode", CommonErrorCode.RESOURCE_NOT_FOUND);
	}

	@Test
	void 남의_추천은_404다() {
		// 403 이면 그 ID 가 존재한다는 사실을 알려주는 셈이다. userRecommendationId 는 연속된
		// 숫자라 남의 것을 찍어볼 수 있으므로 없는 것과 똑같이 다룬다.
		long othersId = saveRecommendation(OTHER_USER_ID);

		assertThatThrownBy(() -> detailService.getDetail(USER_ID, othersId))
				.isInstanceOf(BusinessException.class)
				.hasFieldOrPropertyWithValue("errorCode", CommonErrorCode.RESOURCE_NOT_FOUND);
	}

	@Test
	void 요약이_아직_없으면_null_이다() {
		// 배치가 만들기 전이거나 생성에 실패한 경우. 오류가 아니다.
		long id = saveRecommendation(USER_ID);

		assertThat(detailService.getDetail(USER_ID, id).contextSummary()).isNull();
	}

	@Test
	void 요약이_있으면_그대로_준다() {
		long id = saveRecommendation(USER_ID);
		entityManager.createNativeQuery("UPDATE recommendation_events SET summary = ?2, "
						+ "summary_status = 'COMPLETED' WHERE event_id = ?1")
				.setParameter(1, EVENT_ID).setParameter(2, "금통위가 기준금리를 동결했다.").executeUpdate();
		entityManager.flush();
		entityManager.clear();

		assertThat(detailService.getDetail(USER_ID, id).contextSummary())
				.isEqualTo("금통위가 기준금리를 동결했다.");
	}

	@Test
	void 관련_기사를_관련도_순서_그대로_돌려준다() {
		long id = saveRecommendation(USER_ID);
		long first = insertArticle("관련도 높은 기사", "ECONOMY");
		long second = insertArticle("관련도 낮은 기사", "ECONOMY");
		// Neo4j 가 관련도 순으로 정렬해 준다. 그 차례를 흐트러뜨리지 않아야 한다.
		given(eventArticleRepository.findArticleIdsByEvent(EVENT_ID)).willReturn(List.of(first, second));

		assertThat(detailService.getDetail(USER_ID, id).articles())
				.extracting(RecommendationDetailResponse.Article::articleId)
				.containsExactly(first, second);
	}

	@Test
	void 기사_표시_정보를_채워_준다() {
		long id = saveRecommendation(USER_ID);
		long articleId = insertArticle("한국은행 기준금리 동결", "ECONOMY");
		given(eventArticleRepository.findArticleIdsByEvent(EVENT_ID)).willReturn(List.of(articleId));

		RecommendationDetailResponse.Article article =
				detailService.getDetail(USER_ID, id).articles().get(0);

		assertThat(article.title()).isEqualTo("한국은행 기준금리 동결");
		assertThat(article.organizationName()).isEqualTo("연합뉴스");
		assertThat(article.topicCode()).isEqualTo("ECONOMY");
		assertThat(article.originalUrl()).startsWith("https://yna.co.kr/");
		assertThat(article.publishedAt().getOffset().getTotalSeconds()).isEqualTo(9 * 3600);
	}

	@Test
	void 분석_전_기사는_topicCode_가_null_이다() {
		// 크롤링해 쌓는 기사는 AI 분석 전까지 topic_code 가 비어 있다.
		long id = saveRecommendation(USER_ID);
		long articleId = insertArticle("분석 전 기사", null);
		given(eventArticleRepository.findArticleIdsByEvent(EVENT_ID)).willReturn(List.of(articleId));

		assertThat(detailService.getDetail(USER_ID, id).articles().get(0).topicCode()).isNull();
	}

	@Test
	void 관련_기사가_없으면_빈_목록이다() {
		long id = saveRecommendation(USER_ID);

		assertThat(detailService.getDetail(USER_ID, id).articles()).isEmpty();
	}

	@Test
	void 그래프에만_있고_DB_에_없는_기사는_건너뛴다() {
		long id = saveRecommendation(USER_ID);
		long articleId = insertArticle("살아 있는 기사", "ECONOMY");
		given(eventArticleRepository.findArticleIdsByEvent(EVENT_ID))
				.willReturn(List.of(articleId, 8_888_888L));

		assertThat(detailService.getDetail(USER_ID, id).articles())
				.extracting(RecommendationDetailResponse.Article::articleId)
				.containsExactly(articleId);
	}
}

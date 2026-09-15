package com.starlightnews.backend.domain.recommendation.repository;

import java.time.LocalDateTime;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationEvent;
import com.starlightnews.backend.global.enums.TopicCode;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class RecommendationEventRepositoryTest {

	private static final String EVENT_ID = "00000128-0001-4000-8000-000000000001";

	@Autowired
	private RecommendationEventRepository repository;

	@Autowired
	private TestEntityManager entityManager;

	private RecommendationEvent reload() {
		entityManager.flush();
		entityManager.clear();
		return repository.findById(EVENT_ID).orElseThrow();
	}

	private void setSummary(String summary) {
		entityManager.getEntityManager()
				.createNativeQuery("UPDATE recommendation_events "
						+ "SET summary = ?1, summary_status = 'COMPLETED', summary_generated_at = NOW(6) "
						+ "WHERE event_id = ?2")
				.setParameter(1, summary)
				.setParameter(2, EVENT_ID)
				.executeUpdate();
		entityManager.flush();
		entityManager.clear();
	}

	@Test
	void 없던_Event를_새로_만든다() {
		repository.upsert(EVENT_ID, "한국은행 기준금리 동결", "ECONOMY");

		RecommendationEvent saved = reload();
		assertThat(saved.getEventId()).isEqualTo(EVENT_ID);
		assertThat(saved.getTitle()).isEqualTo("한국은행 기준금리 동결");
		assertThat(saved.getTopicCode()).isEqualTo(TopicCode.ECONOMY);
	}

	@Test
	void 새로_만들면_요약은_아직_요청되지_않은_상태다() {
		repository.upsert(EVENT_ID, "한국은행 기준금리 동결", "ECONOMY");

		RecommendationEvent saved = reload();
		assertThat(saved.getSummary()).isNull();
		assertThat(saved.getSummaryStatus()).isEqualTo("NOT_REQUESTED");
	}

	@Test
	void 이미_있으면_제목과_Topic을_갱신한다() {
		repository.upsert(EVENT_ID, "예전 제목", "SOCIETY");

		repository.upsert(EVENT_ID, "새 제목", "ECONOMY");

		RecommendationEvent saved = reload();
		assertThat(saved.getTitle()).isEqualTo("새 제목");
		assertThat(saved.getTopicCode()).isEqualTo(TopicCode.ECONOMY);
	}

	@Test
	void 갱신해도_이미_만들어진_요약은_지우지_않는다() {
		// 요약은 이 배치가 만들지 않는다. 회차마다 덮어쓰면 매번 다시 만들어야 한다.
		repository.upsert(EVENT_ID, "제목", "ECONOMY");
		setSummary("이미 만들어 둔 요약");

		repository.upsert(EVENT_ID, "제목", "ECONOMY");

		RecommendationEvent saved = reload();
		assertThat(saved.getSummary()).isEqualTo("이미 만들어 둔 요약");
		assertThat(saved.getSummaryStatus()).isEqualTo("COMPLETED");
	}

	@Test
	void 제목이_바뀌면_변경_시각을_남긴다() {
		// 요약을 다시 만들어야 하는지 판단하는 기준이다.
		repository.upsert(EVENT_ID, "예전 제목", "ECONOMY");
		assertThat(reload().getEventUpdatedAt()).isNull();

		repository.upsert(EVENT_ID, "새 제목", "ECONOMY");

		assertThat(reload().getEventUpdatedAt()).isNotNull();
	}

	@Test
	void 제목이_그대로면_변경_시각을_건드리지_않는다() {
		// 내용이 같은데 회차마다 찍으면 매번 요약 재생성 대상이 된다.
		repository.upsert(EVENT_ID, "같은 제목", "ECONOMY");

		repository.upsert(EVENT_ID, "같은 제목", "ECONOMY");

		assertThat(reload().getEventUpdatedAt()).isNull();
	}

	@Test
	void 생성_시각은_처음_저장한_때를_유지한다() {
		repository.upsert(EVENT_ID, "제목", "ECONOMY");
		LocalDateTime createdAt = reload().getCreatedAt();

		repository.upsert(EVENT_ID, "바뀐 제목", "ECONOMY");

		assertThat(reload().getCreatedAt()).isEqualTo(createdAt);
	}
}

package com.starlightnews.backend.domain.article.analysis;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Analyzed;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Halt;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Rejected;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Retryable;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisRecorder.Recorded;
import com.starlightnews.backend.domain.article.analysis.dto.ArticleAnalyzeResponse;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 분석 결과를 실제 MySQL 에 반영해 본다.
 *
 * <p>시도 횟수 갱신은 SET 대입 순서에 따라 결과가 달라져, 엔티티로 만든 테스트 DB 가 아니라 실제
 * MySQL 에서 확인해야 한다.
 */
@SpringBootTest(properties = "app.article.analysis.max-attempts=3")
@ActiveProfiles("test")
@Transactional
class ArticleAnalysisRecorderTest {

	private static final long ORGANIZATION_ID = 93_900L;
	private static final String NODE_ID = "00000021-0920-4000-8000-000000009301";

	@Autowired
	private ArticleAnalysisRecorder recorder;

	@Autowired
	private EntityManager entityManager;

	private long articleId;

	@BeforeEach
	void insertArticle() {
		entityManager.createNativeQuery("INSERT INTO news_organizations (organization_id, name, domain) "
						+ "VALUES (?1, '연합뉴스', 'yna.co.kr') "
						+ "ON DUPLICATE KEY UPDATE organization_id = organization_id")
				.setParameter(1, ORGANIZATION_ID).executeUpdate();
		articleId = insert("https://yna.co.kr/analysis-recorder", "PROCESSING");
	}

	private long insert(String url, String status) {
		entityManager.createNativeQuery("INSERT INTO articles "
						+ "(organization_id, title, url, url_hash, published_at, content, content_type, "
						+ " analysis_status) "
						+ "VALUES (?1, '한국은행 기준금리 동결', ?2, UNHEX(SHA2(?2, 256)), "
						+ " '2026-09-16 09:30:00', '본문', 'FULL_TEXT', ?3)")
				.setParameter(1, ORGANIZATION_ID).setParameter(2, url).setParameter(3, status)
				.executeUpdate();
		entityManager.flush();
		return ((Number) entityManager.createNativeQuery("SELECT article_id FROM articles WHERE url = ?1")
				.setParameter(1, url).getSingleResult()).longValue();
	}

	/** node_id, topic_code, subtopic_code, analysis_status, analysis_attempts */
	private Object[] row() {
		entityManager.flush();
		entityManager.clear();
		return (Object[]) entityManager.createNativeQuery("SELECT node_id, topic_code, subtopic_code, "
						+ "analysis_status, analysis_attempts FROM articles WHERE article_id = ?1")
				.setParameter(1, articleId).getSingleResult();
	}

	private Analyzed analyzed(String topicCode) {
		return new Analyzed(new ArticleAnalyzeResponse.Data(articleId, NODE_ID, "COMPLETED",
				topicCode, "ECONOMY_FINANCE"));
	}

	private Recorded fail() {
		return recorder.record(articleId, new Retryable("EXTRACTION_FAILED"));
	}

	@Test
	void 분석되면_nodeId_와_분류를_채우고_완료로_둔다() {
		assertThat(recorder.record(articleId, analyzed("ECONOMY"))).isEqualTo(Recorded.COMPLETED);

		Object[] row = row();
		assertThat(row[0]).isEqualTo(NODE_ID);
		assertThat(row[1]).isEqualTo("ECONOMY");
		assertThat(row[2]).isEqualTo("ECONOMY_FINANCE");
		assertThat(row[3]).isEqualTo("COMPLETED");
	}

	@Test
	void 분석할_수_없는_기사는_대상에서_뺀다() {
		assertThat(recorder.record(articleId, new Rejected("INTERNAL_API_REJECTED")))
				.isEqualTo(Recorded.DROPPED);

		assertThat(row()[3]).isEqualTo("DROPPED");
	}

	@Test
	void 일시_실패는_횟수를_세고_대기로_남긴다() {
		assertThat(fail()).isEqualTo(Recorded.WILL_RETRY);

		Object[] row = row();
		assertThat(row[3]).isEqualTo("PROCESSING");
		assertThat(((Number) row[4]).intValue()).isEqualTo(1);
	}

	@Test
	void 한도에_닿는_바로_그_실패에서_포기한다() {
		// SET 대입 순서가 틀리면 두 번째 실패에서 FAILED 가 된다.
		assertThat(fail()).isEqualTo(Recorded.WILL_RETRY);
		assertThat(fail()).isEqualTo(Recorded.WILL_RETRY);
		assertThat(row()[3]).isEqualTo("PROCESSING");

		assertThat(fail()).isEqualTo(Recorded.GAVE_UP);

		Object[] row = row();
		assertThat(row[3]).isEqualTo("FAILED");
		assertThat(((Number) row[4]).intValue()).isEqualTo(3);
	}

	@Test
	void 포기한_기사는_더_세지_않는다() {
		fail();
		fail();
		fail();

		assertThat(fail()).isEqualTo(Recorded.UNCHANGED);
		assertThat(((Number) row()[4]).intValue()).isEqualTo(3);
	}

	@Test
	void 회차를_멈추는_실패는_기사를_건드리지_않는다() {
		// 기사 탓이 아니다. 횟수를 올리면 설정을 고치는 사이 멀쩡한 기사가 FAILED 가 된다.
		assertThat(recorder.record(articleId, new Halt("INTERNAL_API_UNAUTHORIZED")))
				.isEqualTo(Recorded.UNCHANGED);

		Object[] row = row();
		assertThat(row[3]).isEqualTo("PROCESSING");
		assertThat(((Number) row[4]).intValue()).isZero();
	}

	@Test
	void 모르는_분류는_반영하지_않고_실패로_센다() {
		// 그대로 넣으면 topic_code 를 TopicCode 로 읽는 조회가 깨진다.
		assertThat(recorder.record(articleId, analyzed("UNKNOWN_TOPIC"))).isEqualTo(Recorded.WILL_RETRY);

		Object[] row = row();
		assertThat(row[0]).isNull();
		assertThat(row[1]).isNull();
		assertThat(((Number) row[4]).intValue()).isEqualTo(1);
	}

	@Test
	void 이미_분석_대기가_아니면_덮어쓰지_않는다() {
		long dropped = insert("https://yna.co.kr/already-dropped", "DROPPED");

		Recorded recorded = recorder.record(dropped, new Analyzed(new ArticleAnalyzeResponse.Data(
				dropped, NODE_ID, "COMPLETED", "ECONOMY", "ECONOMY_FINANCE")));

		assertThat(recorded).isEqualTo(Recorded.UNCHANGED);
		entityManager.clear();
		Object status = entityManager.createNativeQuery(
						"SELECT analysis_status FROM articles WHERE article_id = ?1")
				.setParameter(1, dropped).getSingleResult();
		assertThat(status).isEqualTo("DROPPED");
	}

	@Test
	void 분석에_성공해도_실패_횟수는_그대로_둔다() {
		// 몇 번 만에 성공했는지가 남아 있어야 AI 워커가 얼마나 불안정했는지 볼 수 있다.
		fail();

		recorder.record(articleId, analyzed("ECONOMY"));

		Object[] row = row();
		assertThat(row[3]).isEqualTo("COMPLETED");
		assertThat(((Number) row[4]).intValue()).isEqualTo(1);
	}
}

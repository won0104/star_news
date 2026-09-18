package com.starlightnews.backend.domain.article.analysis;

import java.util.List;

import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.article.repository.ArticleRepository.AnalysisTarget;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.domain.Limit;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 분석 대기열 조회를 실제 MySQL 에서 확인한다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class ArticleAnalysisQueueTest {

	private static final long ORGANIZATION_ID = 92_900L;
	private static final int MAX_ATTEMPTS = 3;

	@Autowired
	private ArticleRepository articleRepository;

	@Autowired
	private EntityManager entityManager;

	@BeforeEach
	void clearQueue() {
		// 다른 테스트가 남긴 대기 기사를 대기열에서 치운다. 트랜잭션이라 테스트가 끝나면 되돌아간다.
		entityManager.createNativeQuery("UPDATE articles SET analysis_status = 'COMPLETED' "
				+ "WHERE analysis_status = 'PROCESSING'").executeUpdate();
		entityManager.createNativeQuery("INSERT INTO news_organizations (organization_id, name, domain) "
						+ "VALUES (?1, '연합뉴스', 'yna.co.kr') "
						+ "ON DUPLICATE KEY UPDATE organization_id = organization_id")
				.setParameter(1, ORGANIZATION_ID).executeUpdate();
	}

	private long insert(String key, String status, String nodeId, int attempts) {
		String url = "https://yna.co.kr/queue/" + key;
		entityManager.createNativeQuery("INSERT INTO articles "
						+ "(organization_id, title, url, url_hash, published_at, content, content_type, "
						+ " analysis_status, node_id, analysis_attempts) "
						+ "VALUES (?1, ?2, ?3, UNHEX(SHA2(?3, 256)), '2026-09-16 09:30:00', '본문', "
						+ " 'FULL_TEXT', ?4, ?5, ?6)")
				.setParameter(1, ORGANIZATION_ID).setParameter(2, "기사 " + key).setParameter(3, url)
				.setParameter(4, status).setParameter(5, nodeId).setParameter(6, attempts)
				.executeUpdate();
		entityManager.flush();
		return ((Number) entityManager.createNativeQuery("SELECT article_id FROM articles WHERE url = ?1")
				.setParameter(1, url).getSingleResult()).longValue();
	}

	private List<Long> queue(int limit) {
		return articleRepository.findAnalysisQueue(MAX_ATTEMPTS, Limit.of(limit)).stream()
				.map(AnalysisTarget::getArticleId).toList();
	}

	@Test
	void 분석_대기_중인_기사를_고른다() {
		long pending = insert("pending", "PROCESSING", null, 0);

		assertThat(queue(10)).containsExactly(pending);
	}

	@Test
	void 오래된_기사부터_고른다() {
		long first = insert("first", "PROCESSING", null, 0);
		long second = insert("second", "PROCESSING", null, 0);

		assertThat(queue(10)).containsExactly(first, second);
	}

	@Test
	void 정해진_개수만큼만_고른다() {
		insert("a", "PROCESSING", null, 0);
		insert("b", "PROCESSING", null, 0);
		insert("c", "PROCESSING", null, 0);

		assertThat(queue(2)).hasSize(2);
	}

	@Test
	void 끝났거나_뺀_기사는_고르지_않는다() {
		insert("completed", "COMPLETED", "00000021-0920-4000-8000-000000009201", 0);
		insert("dropped", "DROPPED", null, 0);
		insert("failed", "FAILED", null, 3);

		assertThat(queue(10)).isEmpty();
	}

	@Test
	void 시도_횟수를_다_쓴_기사는_고르지_않는다() {
		long retry = insert("retry", "PROCESSING", null, 2);
		insert("exhausted", "PROCESSING", null, 3);

		assertThat(queue(10)).containsExactly(retry);
	}

	@Test
	void 이미_그래프에_반영된_기사는_고르지_않는다() {
		// Spring 이 응답을 받기 전에 끊겼어도 FastAPI 는 끝까지 반영한다. 다시 부를 이유가 없다.
		insert("already-in-graph", "PROCESSING", "00000021-0920-4000-8000-000000009202", 0);

		assertThat(queue(10)).isEmpty();
	}

	@Test
	void 대기_전체_수는_회차_상한과_무관하게_센다() {
		insert("a", "PROCESSING", null, 0);
		insert("b", "PROCESSING", null, 2);
		insert("c", "PROCESSING", null, 0);
		insert("exhausted", "PROCESSING", null, 3);
		insert("done", "COMPLETED", "00000021-0920-4000-8000-000000009203", 0);

		assertThat(queue(1)).hasSize(1);
		assertThat(articleRepository.countAnalysisQueue(MAX_ATTEMPTS)).isEqualTo(3);
	}

	@Test
	void 대기가_없으면_가장_오래_기다린_시간도_없다() {
		assertThat(articleRepository.findOldestAnalysisWaitMinutes(MAX_ATTEMPTS)).isNull();
	}

	@Test
	void 가장_오래_기다린_기사가_수집된_지_몇_분인지_잰다() {
		long old = insert("old", "PROCESSING", null, 0);
		insert("new", "PROCESSING", null, 0);
		// DB 시각 기준으로 뺀다. 애플리케이션 시각과 견주면 서버 시간대에 따라 어긋난다.
		entityManager.createNativeQuery("UPDATE articles SET created_at = NOW(6) - INTERVAL 95 MINUTE "
				+ "WHERE article_id = ?1").setParameter(1, old).executeUpdate();
		entityManager.flush();

		// 분 단위 내림이다. 기사 시각은 마이크로초까지 찍혀 94분으로 떨어질 수 있다.
		assertThat(articleRepository.findOldestAnalysisWaitMinutes(MAX_ATTEMPTS)).isBetween(94L, 96L);
	}

	@Test
	void 분석_요청에_필요한_값을_함께_가져온다() {
		long id = insert("fields", "PROCESSING", null, 0);

		AnalysisTarget target = articleRepository.findAnalysisQueue(MAX_ATTEMPTS, Limit.of(10)).get(0);

		assertThat(target.getArticleId()).isEqualTo(id);
		assertThat(target.getTitle()).isEqualTo("기사 fields");
		assertThat(target.getContent()).isEqualTo("본문");
		assertThat(target.getOrganizationId()).isEqualTo(ORGANIZATION_ID);
		assertThat(target.getOrganizationName()).isEqualTo("연합뉴스");
		assertThat(target.getPublishedAt()).isNotNull();
	}
}

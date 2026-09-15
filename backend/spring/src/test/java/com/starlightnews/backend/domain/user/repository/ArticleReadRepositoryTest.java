package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.domain.NewsOrganization;
import com.starlightnews.backend.domain.user.domain.ArticleRead;
import com.starlightnews.backend.domain.user.domain.ArticleReadId;
import com.starlightnews.backend.support.TestFixtures;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.groups.Tuple.tuple;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class ArticleReadRepositoryTest {

	@Autowired
	private ArticleReadRepository articleReadRepository;

	@Autowired
	private TestEntityManager entityManager;

	@BeforeEach
	void insertReferencedRows() {
		TestFixtures.insertUsers(entityManager, 1L, 2L);
	}

	private Article article(NewsOrganization org, String title, String topicCode) {
		return article(org, title, topicCode, null);
	}

	private Article article(NewsOrganization org, String title, String topicCode, String summary) {
		Article article = new Article(title, LocalDateTime.of(2024, 1, 11, 9, 0), org);
		if (topicCode != null) {
			ReflectionTestUtils.setField(article, "topicCode", topicCode);
		}
		if (summary != null) {
			ReflectionTestUtils.setField(article, "summary", summary);
		}
		return entityManager.persist(article);
	}

	@Test
	void countReadArticlesByTopic는_사용자가_읽은_기사를_Topic별로_집계한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article economyA = article(org, "제목1", "ECONOMY");
		Article economyB = article(org, "제목2", "ECONOMY");
		Article society = article(org, "제목3", "SOCIETY");
		Article noTopic = article(org, "제목4", null);
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);

		entityManager.persist(new ArticleRead(new ArticleReadId(1L, economyA.getArticleId()), now, now, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, economyB.getArticleId()), now, now, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, society.getArticleId()), now, now, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, noTopic.getArticleId()), now, now, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(2L, economyA.getArticleId()), now, now, 1)); // 다른 사용자
		entityManager.flush();
		entityManager.clear();

		List<ArticleReadRepository.TopicReadCount> counts = articleReadRepository.countReadArticlesByTopic(1L);

		assertThat(counts)
				.extracting(ArticleReadRepository.TopicReadCount::getTopicCode,
						ArticleReadRepository.TopicReadCount::getCount)
				.containsExactlyInAnyOrder(tuple("ECONOMY", 2L), tuple("SOCIETY", 1L));
	}

	@Test
	void 읽은_기사가_없으면_빈_목록이다() {
		assertThat(articleReadRepository.countReadArticlesByTopic(999L)).isEmpty();
	}

	@Test
	void findFirstReadPage는_후보_기사_중_읽은_것만_최신읽은순으로_반환하고_요약을_포함한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article a1 = article(org, "기준금리 동결", "ECONOMY", "한국은행이 금리를 동결했다.");
		Article a2 = article(org, "환율 급등", "ECONOMY", null);
		Article a3 = article(org, "의대 증원", "SOCIETY", null); // 후보(관련 기사)가 아님

		LocalDateTime older = LocalDateTime.of(2026, 8, 30, 9, 0);
		LocalDateTime newer = LocalDateTime.of(2026, 8, 31, 9, 10);
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a1.getArticleId()), older, older, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a2.getArticleId()), newer, newer, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a3.getArticleId()), newer, newer, 1));
		entityManager.flush();
		entityManager.clear();

		List<ArticleReadRepository.ReadArticleRow> page = articleReadRepository.findFirstReadPage(
				1L, List.of(a1.getArticleId(), a2.getArticleId()), PageRequest.of(0, 10));

		assertThat(page).extracting(ArticleReadRepository.ReadArticleRow::getArticleId)
				.containsExactly(a2.getArticleId(), a1.getArticleId()); // 최근 읽은 순
		assertThat(page.get(1).getTitle()).isEqualTo("기준금리 동결");
		assertThat(page.get(1).getOrganizationName()).isEqualTo("연합뉴스");
		assertThat(page.get(1).getTopicCode()).isEqualTo("ECONOMY");
		assertThat(page.get(1).getSummary()).isEqualTo("한국은행이 금리를 동결했다.");
		assertThat(page.get(0).getSummary()).isNull();
	}

	@Test
	void findFirstReadPage는_다른_사용자의_열람_기록은_제외한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article a1 = article(org, "기준금리 동결", "ECONOMY");
		LocalDateTime now = LocalDateTime.of(2026, 8, 31, 9, 10);
		entityManager.persist(new ArticleRead(new ArticleReadId(2L, a1.getArticleId()), now, now, 1));
		entityManager.flush();
		entityManager.clear();

		List<ArticleReadRepository.ReadArticleRow> page = articleReadRepository.findFirstReadPage(
				1L, List.of(a1.getArticleId()), PageRequest.of(0, 10));

		assertThat(page).isEmpty();
	}

	@Test
	void findFirstReadPage는_Pageable_limit을_따른다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article a1 = article(org, "제목1", "ECONOMY");
		Article a2 = article(org, "제목2", "ECONOMY");
		LocalDateTime t1 = LocalDateTime.of(2026, 8, 30, 9, 0);
		LocalDateTime t2 = LocalDateTime.of(2026, 8, 31, 9, 0);
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a1.getArticleId()), t1, t1, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a2.getArticleId()), t2, t2, 1));
		entityManager.flush();
		entityManager.clear();

		List<ArticleReadRepository.ReadArticleRow> page = articleReadRepository.findFirstReadPage(
				1L, List.of(a1.getArticleId(), a2.getArticleId()), PageRequest.of(0, 1));

		assertThat(page).hasSize(1);
		assertThat(page.get(0).getArticleId()).isEqualTo(a2.getArticleId()); // 최신 것 하나만
	}

	@Test
	void findNextReadPage는_커서_위치_다음부터_반환한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article a1 = article(org, "제목1", "ECONOMY");
		Article a2 = article(org, "제목2", "ECONOMY");
		Article a3 = article(org, "제목3", "ECONOMY");
		LocalDateTime t1 = LocalDateTime.of(2026, 8, 29, 9, 0);
		LocalDateTime t2 = LocalDateTime.of(2026, 8, 30, 9, 0);
		LocalDateTime t3 = LocalDateTime.of(2026, 8, 31, 9, 0);
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a1.getArticleId()), t1, t1, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a2.getArticleId()), t2, t2, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a3.getArticleId()), t3, t3, 1));
		entityManager.flush();
		entityManager.clear();

		List<ArticleReadRepository.ReadArticleRow> page = articleReadRepository.findNextReadPage(
				1L, List.of(a1.getArticleId(), a2.getArticleId(), a3.getArticleId()),
				t2, a2.getArticleId(), PageRequest.of(0, 10));

		assertThat(page).extracting(ArticleReadRepository.ReadArticleRow::getArticleId)
				.containsExactly(a1.getArticleId()); // t2 보다 이전(t1)만
	}

	@Test
	void findFirstHistoryPage는_topicCode_없으면_전체_열람기록을_최신순으로_반환한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article a1 = article(org, "기준금리 동결", "ECONOMY");
		Article a2 = article(org, "의대 증원", "SOCIETY");
		LocalDateTime older = LocalDateTime.of(2026, 8, 30, 9, 0);
		LocalDateTime newer = LocalDateTime.of(2026, 8, 31, 9, 10);
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a1.getArticleId()), older, older, 3));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a2.getArticleId()), newer, newer, 1));
		entityManager.flush();
		entityManager.clear();

		List<ArticleReadRepository.HistoryRow> page = articleReadRepository.findFirstHistoryPage(
				1L, null, PageRequest.of(0, 10));

		assertThat(page).extracting(ArticleReadRepository.HistoryRow::getArticleId)
				.containsExactly(a2.getArticleId(), a1.getArticleId());
		assertThat(page.get(1).getClickCount()).isEqualTo(3);
	}

	@Test
	void findFirstHistoryPage는_topicCode가_있으면_그_토픽만_반환한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article a1 = article(org, "기준금리 동결", "ECONOMY");
		Article a2 = article(org, "의대 증원", "SOCIETY");
		LocalDateTime now = LocalDateTime.of(2026, 8, 31, 9, 0);
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a1.getArticleId()), now, now, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a2.getArticleId()), now, now, 1));
		entityManager.flush();
		entityManager.clear();

		List<ArticleReadRepository.HistoryRow> page = articleReadRepository.findFirstHistoryPage(
				1L, "ECONOMY", PageRequest.of(0, 10));

		assertThat(page).extracting(ArticleReadRepository.HistoryRow::getArticleId)
				.containsExactly(a1.getArticleId());
	}

	@Test
	void findFirstHistoryPage는_다른_사용자_기록은_제외한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article a1 = article(org, "기준금리 동결", "ECONOMY");
		LocalDateTime now = LocalDateTime.of(2026, 8, 31, 9, 0);
		entityManager.persist(new ArticleRead(new ArticleReadId(2L, a1.getArticleId()), now, now, 1));
		entityManager.flush();
		entityManager.clear();

		assertThat(articleReadRepository.findFirstHistoryPage(1L, null, PageRequest.of(0, 10))).isEmpty();
	}

	@Test
	void findNextHistoryPage는_커서_다음부터_topicCode_필터와_함께_적용된다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article a1 = article(org, "제목1", "ECONOMY");
		Article a2 = article(org, "제목2", "ECONOMY");
		Article a3 = article(org, "제목3", "SOCIETY");
		LocalDateTime t1 = LocalDateTime.of(2026, 8, 29, 9, 0);
		LocalDateTime t2 = LocalDateTime.of(2026, 8, 30, 9, 0);
		LocalDateTime t3 = LocalDateTime.of(2026, 8, 31, 9, 0);
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a1.getArticleId()), t1, t1, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a2.getArticleId()), t2, t2, 1));
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, a3.getArticleId()), t3, t3, 1)); // SOCIETY, 커서보다 최신
		entityManager.flush();
		entityManager.clear();

		List<ArticleReadRepository.HistoryRow> page = articleReadRepository.findNextHistoryPage(
				1L, "ECONOMY", t2, a2.getArticleId(), PageRequest.of(0, 10));

		assertThat(page).extracting(ArticleReadRepository.HistoryRow::getArticleId)
				.containsExactly(a1.getArticleId()); // SOCIETY(a3)는 필터로 제외, ECONOMY 중 t2 이전인 a1만
	}

	@Test
	void upsertRead는_처음이면_click_count_1로_INSERT하고_1을_반환한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = article(org, "제목1", "ECONOMY");
		LocalDateTime now = LocalDateTime.of(2026, 8, 29, 9, 0);
		entityManager.flush();

		int affected = articleReadRepository.upsertRead(1L, article.getArticleId(), now);
		entityManager.clear();

		assertThat(affected).isEqualTo(1); // INSERT
		ArticleRead found = entityManager.find(ArticleRead.class,
				new ArticleReadId(1L, article.getArticleId()));
		assertThat(found.getClickCount()).isEqualTo(1);
		assertThat(found.getFirstReadAt()).isEqualTo(now);
		assertThat(found.getLastReadAt()).isEqualTo(now);
	}

	@Test
	void upsertRead는_재열람이면_first_read_at을_유지하고_2를_반환한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = article(org, "제목1", "ECONOMY");
		LocalDateTime first = LocalDateTime.of(2026, 8, 29, 9, 0);
		LocalDateTime later = LocalDateTime.of(2026, 8, 31, 14, 30);
		ArticleReadId id = new ArticleReadId(1L, article.getArticleId());
		entityManager.persist(new ArticleRead(id, first, first, 1));
		entityManager.flush();

		int affected = articleReadRepository.upsertRead(1L, article.getArticleId(), later);
		entityManager.clear();

		assertThat(affected).isEqualTo(2); // 기존 행 갱신
		ArticleRead reloaded = entityManager.find(ArticleRead.class, id);
		assertThat(reloaded.getClickCount()).isEqualTo(2);
		assertThat(reloaded.getLastReadAt()).isEqualTo(later);
		assertThat(reloaded.getFirstReadAt()).isEqualTo(first);
	}

	@Test
	void upsertRead는_같은_기사라도_다른_사용자의_Row는_건드리지_않는다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = article(org, "제목1", "ECONOMY");
		LocalDateTime first = LocalDateTime.of(2026, 8, 29, 9, 0);
		LocalDateTime later = LocalDateTime.of(2026, 8, 31, 14, 30);
		ArticleReadId others = new ArticleReadId(2L, article.getArticleId());
		entityManager.persist(new ArticleRead(new ArticleReadId(1L, article.getArticleId()), first, first, 1));
		entityManager.persist(new ArticleRead(others, first, first, 1));
		entityManager.flush();

		articleReadRepository.upsertRead(1L, article.getArticleId(), later);
		entityManager.clear();

		ArticleRead untouched = entityManager.find(ArticleRead.class, others);
		assertThat(untouched.getClickCount()).isEqualTo(1);
		assertThat(untouched.getLastReadAt()).isEqualTo(first);
	}
}

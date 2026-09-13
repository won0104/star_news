package com.starlightnews.backend.domain.article.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.domain.NewsOrganization;
import com.starlightnews.backend.global.enums.AnalysisStatus;
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
class ArticleRepositoryTest {

	@Autowired
	private ArticleRepository articleRepository;

	@Autowired
	private TestEntityManager entityManager;

	@Test
	void articleId_목록으로_기사를_언론사와_함께_조회한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article a1 = entityManager.persist(new Article("제목1", LocalDateTime.of(2024, 1, 11, 9, 0), org));
		Article a2 = entityManager.persist(new Article("제목2", LocalDateTime.of(2024, 1, 12, 9, 0), org));
		entityManager.persist(new Article("제목3", LocalDateTime.of(2024, 1, 13, 9, 0), org));
		entityManager.flush();
		entityManager.clear();

		List<Article> found = articleRepository.findAllWithOrganizationByArticleIdIn(
				List.of(a1.getArticleId(), a2.getArticleId()));

		assertThat(found).extracting(Article::getTitle).containsExactlyInAnyOrder("제목1", "제목2");
		assertThat(found).allSatisfy(a -> assertThat(a.getOrganization().getName()).isEqualTo("연합뉴스"));
	}

	@Test
	void 존재하지_않는_articleId면_빈_목록이다() {
		assertThat(articleRepository.findAllWithOrganizationByArticleIdIn(List.of(999L))).isEmpty();
	}

	@Test
	void 요청한_ID_중_COMPLETED_기사_ID만_반환한다() {
		NewsOrganization organization = entityManager.persist(new NewsOrganization("연합뉴스"));
		LocalDateTime publishedAt = LocalDateTime.of(2026, 9, 1, 9, 0);
		Article completed = entityManager.persist(new Article(
				"분석 완료", publishedAt, organization, null, AnalysisStatus.COMPLETED));
		Article processing = entityManager.persist(new Article(
				"분석 중", publishedAt, organization, null, AnalysisStatus.PROCESSING));
		entityManager.flush();

		List<Long> found = articleRepository.findArticleIdsByIdInAndAnalysisStatus(
				List.of(completed.getArticleId(), processing.getArticleId(), 999L),
				AnalysisStatus.COMPLETED);

		assertThat(found).containsExactly(completed.getArticleId());
	}
}

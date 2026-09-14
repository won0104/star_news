package com.starlightnews.backend.domain.article.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.domain.NewsOrganization;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.util.ReflectionTestUtils;

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
	void findGraphRefByArticleId는_분석된_기사의_nodeId를_반환한다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = new Article("제목1", LocalDateTime.of(2024, 1, 11, 9, 0), org);
		ReflectionTestUtils.setField(article, "nodeId", "00000010-0920-4000-8000-000000000001");
		entityManager.persist(article);
		entityManager.flush();
		entityManager.clear();

		ArticleRepository.ArticleGraphRef ref = articleRepository
				.findGraphRefByArticleId(article.getArticleId()).orElseThrow();

		assertThat(ref.getNodeId()).isEqualTo("00000010-0920-4000-8000-000000000001");
	}

	@Test
	void findGraphRefByArticleId는_분석_전_기사면_nodeId가_null이다() {
		NewsOrganization org = entityManager.persist(new NewsOrganization("연합뉴스"));
		Article article = entityManager.persist(
				new Article("제목1", LocalDateTime.of(2024, 1, 11, 9, 0), org));
		entityManager.flush();
		entityManager.clear();

		ArticleRepository.ArticleGraphRef ref = articleRepository
				.findGraphRefByArticleId(article.getArticleId()).orElseThrow();

		// 기사 자체는 있으므로 빈 Optional 이 아니다. 둘을 구분해야 404 와 Neo4j 건너뛰기가 갈린다.
		assertThat(ref.getArticleId()).isEqualTo(article.getArticleId());
		assertThat(ref.getNodeId()).isNull();
	}

	@Test
	void findGraphRefByArticleId는_없는_기사면_빈_Optional이다() {
		assertThat(articleRepository.findGraphRefByArticleId(999L)).isEmpty();
	}
}

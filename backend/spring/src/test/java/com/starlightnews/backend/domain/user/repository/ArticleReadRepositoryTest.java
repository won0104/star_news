package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.domain.NewsOrganization;
import com.starlightnews.backend.domain.user.domain.ArticleRead;
import com.starlightnews.backend.domain.user.domain.ArticleReadId;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
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

	private Article article(NewsOrganization org, String title, String topicCode) {
		Article article = new Article(title, LocalDateTime.of(2024, 1, 11, 9, 0), org);
		if (topicCode != null) {
			ReflectionTestUtils.setField(article, "topicCode", topicCode);
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
}

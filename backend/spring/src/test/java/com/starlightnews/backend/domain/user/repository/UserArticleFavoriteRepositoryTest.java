package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.user.domain.UserArticleFavorite;
import com.starlightnews.backend.domain.user.domain.UserArticleFavoriteId;
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
class UserArticleFavoriteRepositoryTest {

	@Autowired
	private UserArticleFavoriteRepository repository;

	@Autowired
	private TestEntityManager entityManager;

	private void favorite(long userId, long articleId) {
		entityManager.persist(new UserArticleFavorite(
				new UserArticleFavoriteId(userId, articleId), LocalDateTime.now()));
		entityManager.flush();
	}

	@Test
	void 주어진_articleId_중_해당_유저가_즐겨찾기한_것만_반환한다() {
		favorite(1L, 10L);
		favorite(1L, 20L);
		favorite(2L, 10L);

		assertThat(repository.findFavoritedArticleIds(1L, List.of(10L, 20L, 30L)))
				.containsExactlyInAnyOrder(10L, 20L);
		assertThat(repository.findFavoritedArticleIds(2L, List.of(10L, 20L)))
				.containsExactly(10L);
	}

	@Test
	void 즐겨찾기가_없으면_빈_목록이다() {
		assertThat(repository.findFavoritedArticleIds(1L, List.of(10L, 20L))).isEmpty();
	}
}

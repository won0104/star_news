package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.domain.NewsOrganization;
import com.starlightnews.backend.domain.user.domain.UserArticleFavorite;
import com.starlightnews.backend.domain.user.domain.UserArticleFavoriteId;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository.ArticleBookmarkRow;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.PageRequest;
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
		favorite(userId, articleId, LocalDateTime.now());
	}

	private void favorite(long userId, long articleId, LocalDateTime favoritedAt) {
		entityManager.persist(new UserArticleFavorite(
				new UserArticleFavoriteId(userId, articleId), favoritedAt));
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

	@Test
	void 공개_기사_북마크를_등록시각과_articleId_내림차순으로_조회한다() {
		NewsOrganization organization = entityManager.persist(new NewsOrganization("연합뉴스"));
		LocalDateTime publishedAt = LocalDateTime.of(2026, 8, 31, 9, 0);
		Article older = entityManager.persist(new Article(
				"오래된 북마크", publishedAt, organization, "오래된 요약", AnalysisStatus.COMPLETED));
		Article tieLowerId = entityManager.persist(new Article(
				"같은 시각 낮은 ID", publishedAt, organization, null, AnalysisStatus.COMPLETED));
		Article tieHigherId = entityManager.persist(new Article(
				"같은 시각 높은 ID", publishedAt, organization, "최신 요약", AnalysisStatus.COMPLETED));
		Article processing = entityManager.persist(new Article(
				"분석 중", publishedAt, organization, null, AnalysisStatus.PROCESSING));
		LocalDateTime olderTime = LocalDateTime.of(2026, 9, 1, 8, 0);
		LocalDateTime newestTime = LocalDateTime.of(2026, 9, 1, 9, 0);
		favorite(1L, older.getArticleId(), olderTime);
		favorite(1L, tieLowerId.getArticleId(), newestTime);
		favorite(1L, tieHigherId.getArticleId(), newestTime);
		favorite(1L, processing.getArticleId(), newestTime.plusHours(1));
		favorite(2L, older.getArticleId(), newestTime.plusHours(2));

		List<ArticleBookmarkRow> rows = repository.findFirstArticleBookmarkPage(
				1L, AnalysisStatus.COMPLETED, PageRequest.of(0, 10));

		assertThat(rows).extracting(ArticleBookmarkRow::getArticleId)
				.containsExactly(tieHigherId.getArticleId(), tieLowerId.getArticleId(), older.getArticleId());
		assertThat(rows.get(0).getPublisher()).isEqualTo("연합뉴스");
		assertThat(rows.get(0).getSummary()).isEqualTo("최신 요약");
		assertThat(rows.get(0).getPublishedAt()).isEqualTo(publishedAt);
		assertThat(rows.get(0).getBookmarkedAt()).isEqualTo(newestTime);
	}

	@Test
	void 다음_페이지는_커서_복합키보다_뒤의_항목만_조회한다() {
		NewsOrganization organization = entityManager.persist(new NewsOrganization("한국일보"));
		LocalDateTime publishedAt = LocalDateTime.of(2026, 8, 31, 9, 0);
		Article lowerId = entityManager.persist(new Article(
				"낮은 ID", publishedAt, organization, null, AnalysisStatus.COMPLETED));
		Article cursorArticle = entityManager.persist(new Article(
				"커서 기사", publishedAt, organization, null, AnalysisStatus.COMPLETED));
		Article higherId = entityManager.persist(new Article(
				"높은 ID", publishedAt, organization, null, AnalysisStatus.COMPLETED));
		LocalDateTime sameTime = LocalDateTime.of(2026, 9, 1, 9, 0);
		favorite(1L, lowerId.getArticleId(), sameTime);
		favorite(1L, cursorArticle.getArticleId(), sameTime);
		favorite(1L, higherId.getArticleId(), sameTime);

		List<ArticleBookmarkRow> rows = repository.findNextArticleBookmarkPage(
				1L,
				AnalysisStatus.COMPLETED,
				sameTime,
				cursorArticle.getArticleId(),
				PageRequest.of(0, 10));

		assertThat(rows).extracting(ArticleBookmarkRow::getArticleId)
				.containsExactly(lowerId.getArticleId());
	}
}

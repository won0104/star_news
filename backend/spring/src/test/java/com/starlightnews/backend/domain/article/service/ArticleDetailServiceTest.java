package com.starlightnews.backend.domain.article.service;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.util.Optional;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.domain.NewsOrganization;
import com.starlightnews.backend.domain.article.dto.ArticleDetailResponse;
import com.starlightnews.backend.domain.article.exception.ArticleErrorCode;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.user.domain.UserArticleFavoriteId;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class ArticleDetailServiceTest {

	private static final Long ARTICLE_ID = 101L;
	private static final Long USER_ID = 1L;

	@Mock
	private ArticleRepository articleRepository;

	@Mock
	private UserArticleFavoriteRepository userArticleFavoriteRepository;

	@InjectMocks
	private ArticleDetailService articleDetailService;

	@Test
	void 비회원은_저장된_기사_상세를_bookmarked_false로_조회한다() {
		Article article = article("저장된 요약");
		given(articleRepository.findDetailByArticleId(ARTICLE_ID, AnalysisStatus.COMPLETED))
				.willReturn(Optional.of(article));

		ArticleDetailResponse response = articleDetailService.getDetail(ARTICLE_ID, null);

		assertThat(response.articleId()).isEqualTo(ARTICLE_ID);
		assertThat(response.title()).isEqualTo("국방부, 한미 연합훈련 일정 발표");
		assertThat(response.organizationName()).isEqualTo("연합뉴스");
		assertThat(response.publishedAt()).isEqualTo(OffsetDateTime.parse("2026-08-31T10:00:00+09:00"));
		assertThat(response.originalUrl()).isEqualTo("https://news.example.com/articles/101");
		assertThat(response.bookmarked()).isFalse();
		verifyNoInteractions(userArticleFavoriteRepository);
	}

	@Test
	void 요약이_없어도_기사_상세를_반환한다() {
		Article article = article(null);
		given(articleRepository.findDetailByArticleId(ARTICLE_ID, AnalysisStatus.COMPLETED))
				.willReturn(Optional.of(article));
		given(userArticleFavoriteRepository.existsById(
				new UserArticleFavoriteId(USER_ID, ARTICLE_ID))).willReturn(true);

		ArticleDetailResponse response = articleDetailService.getDetail(ARTICLE_ID, USER_ID);

		assertThat(response.articleId()).isEqualTo(ARTICLE_ID);
		assertThat(response.title()).isEqualTo("국방부, 한미 연합훈련 일정 발표");
		assertThat(response.bookmarked()).isTrue();
	}

	@Test
	void 기사가_없으면_ARTICLE_NOT_FOUND_예외다() {
		given(articleRepository.findDetailByArticleId(ARTICLE_ID, AnalysisStatus.COMPLETED))
				.willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> articleDetailService.getDetail(ARTICLE_ID, USER_ID));

		assertThat(thrown).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) thrown).getErrorCode()).isEqualTo(ArticleErrorCode.ARTICLE_NOT_FOUND);
		verify(userArticleFavoriteRepository, never()).existsById(new UserArticleFavoriteId(USER_ID, ARTICLE_ID));
	}

	@Test
	void 기사_조회가_실패하면_ARTICLE_DETAIL_QUERY_FAILED_예외다() {
		given(articleRepository.findDetailByArticleId(ARTICLE_ID, AnalysisStatus.COMPLETED))
				.willThrow(new DataAccessResourceFailureException("database unavailable"));

		Throwable thrown = catchThrowable(() -> articleDetailService.getDetail(ARTICLE_ID, USER_ID));

		assertThat(thrown).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) thrown).getErrorCode())
				.isEqualTo(ArticleErrorCode.ARTICLE_DETAIL_QUERY_FAILED);
		verifyNoInteractions(userArticleFavoriteRepository);
	}

	@Test
	void 북마크_조회가_실패하면_ARTICLE_DETAIL_QUERY_FAILED_예외다() {
		given(articleRepository.findDetailByArticleId(ARTICLE_ID, AnalysisStatus.COMPLETED))
				.willReturn(Optional.of(article(null)));
		given(userArticleFavoriteRepository.existsById(
				new UserArticleFavoriteId(USER_ID, ARTICLE_ID)))
				.willThrow(new DataAccessResourceFailureException("database unavailable"));

		Throwable thrown = catchThrowable(() -> articleDetailService.getDetail(ARTICLE_ID, USER_ID));

		assertThat(thrown).isInstanceOf(BusinessException.class);
		assertThat(((BusinessException) thrown).getErrorCode())
				.isEqualTo(ArticleErrorCode.ARTICLE_DETAIL_QUERY_FAILED);
	}

	private Article article(String summary) {
		Article article = new Article(
				"국방부, 한미 연합훈련 일정 발표",
				LocalDateTime.of(2026, 8, 31, 10, 0),
				new NewsOrganization("연합뉴스"),
				summary,
				AnalysisStatus.COMPLETED);
		ReflectionTestUtils.setField(article, "articleId", ARTICLE_ID);
		ReflectionTestUtils.setField(article, "url", "https://news.example.com/articles/101");
		return article;
	}
}

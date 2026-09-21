package com.starlightnews.backend.domain.article.service;

import java.time.ZoneOffset;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.dto.ArticleDetailResponse;
import com.starlightnews.backend.domain.article.exception.ArticleErrorCode;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.user.domain.UserArticleFavoriteId;
import com.starlightnews.backend.domain.user.repository.UserArticleFavoriteRepository;
import com.starlightnews.backend.global.enums.AnalysisStatus;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;

/** 기사 상세 정보와 요약, 로그인 사용자의 북마크 여부를 조회한다. */
@Slf4j
@Service
@RequiredArgsConstructor
public class ArticleDetailService {

	private static final ZoneOffset KOREA_OFFSET = ZoneOffset.ofHours(9);

	private final ArticleRepository articleRepository;
	private final UserArticleFavoriteRepository userArticleFavoriteRepository;

	/** 기사 상세를 조회한다. 요약 조회·생성은 별도의 summary API가 담당한다. */
	public ArticleDetailResponse getDetail(Long articleId, Long userId) {
		Article article = findArticle(articleId);
		boolean bookmarked = isBookmarked(userId, articleId);

		return new ArticleDetailResponse(
				article.getArticleId(),
				article.getTitle(),
				article.getOrganization().getName(),
				article.getPublishedAt().atOffset(KOREA_OFFSET),
				article.getUrl(),
				bookmarked);
	}

	private Article findArticle(Long articleId) {
		try {
			return articleRepository.findDetailByArticleId(articleId, AnalysisStatus.COMPLETED)
					.orElseThrow(() -> new BusinessException(ArticleErrorCode.ARTICLE_NOT_FOUND));
		} catch (DataAccessException exception) {
			log.error("기사 상세 조회에 실패했습니다. articleId={}", articleId, exception);
			throw new BusinessException(ArticleErrorCode.ARTICLE_DETAIL_QUERY_FAILED);
		}
	}

	private boolean isBookmarked(Long userId, Long articleId) {
		if (userId == null) {
			return false;
		}

		try {
			return userArticleFavoriteRepository.existsById(
					new UserArticleFavoriteId(userId, articleId));
		} catch (DataAccessException exception) {
			log.error("기사 북마크 여부 조회에 실패했습니다. userId={}, articleId={}",
					userId, articleId, exception);
			throw new BusinessException(ArticleErrorCode.ARTICLE_DETAIL_QUERY_FAILED);
		}
	}
}

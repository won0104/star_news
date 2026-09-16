package com.starlightnews.backend.domain.recommendation.service;

import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

import com.starlightnews.backend.domain.article.domain.Article;
import com.starlightnews.backend.domain.article.repository.ArticleRepository;
import com.starlightnews.backend.domain.recommendation.domain.RecommendationEvent;
import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationDetailResponse;
import com.starlightnews.backend.domain.recommendation.repository.EventArticleRepository;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationEventRepository;
import com.starlightnews.backend.domain.recommendation.repository.UserRecommendationRepository;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 추천 Event 상세를 조회한다.
 *
 * <p>요약은 여기서 만들지 않는다. 추천 배치가 회차를 저장한 직후에 만들어 두므로 읽기만 한다.
 */
@Service
@RequiredArgsConstructor
public class RecommendationDetailService {

	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	private final UserRecommendationRepository userRecommendationRepository;
	private final RecommendationEventRepository eventRepository;
	private final EventArticleRepository eventArticleRepository;
	private final ArticleRepository articleRepository;

	/**
	 * 추천 하나의 Event 정보와 관련 기사를 조회한다.
	 * @throws BusinessException 추천이 없거나 다른 사용자의 것이면 RESOURCE_NOT_FOUND
	 */
	@Transactional(readOnly = true)
	public RecommendationDetailResponse getDetail(Long userId, Long userRecommendationId) {
		UserRecommendation recommendation = userRecommendationRepository.findById(userRecommendationId)
				.filter(found -> found.getUserId().equals(userId))
				.orElseThrow(() -> new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND));

		RecommendationEvent event = eventRepository.findById(recommendation.getEventId())
				.orElseThrow(() -> new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND));

		return new RecommendationDetailResponse(
				recommendation.getUserRecommendationId(),
				event.getEventId(),
				event.getTitle(),
				event.getTopicCode(),
				event.getSummary(),
				relatedArticles(event.getEventId()));
	}

	/**
	 * Event 를 다루는 기사를 관련도 순으로 모은다.
	 *
	 * <p>차례는 Neo4j 가 정한다. MySQL 조회 결과를 그 차례에 맞춰 다시 늘어놓는다.
	 * 그래프에는 있는데 MySQL 에 없는 기사는 건너뛴다.
	 */
	private List<RecommendationDetailResponse.Article> relatedArticles(String eventId) {
		List<Long> orderedIds = eventArticleRepository.findArticleIdsByEvent(eventId);
		if (orderedIds.isEmpty()) {
			return List.of();
		}

		Map<Long, Article> articles = articleRepository
				.findAllWithOrganizationByArticleIdIn(orderedIds).stream()
				.collect(Collectors.toMap(Article::getArticleId, Function.identity()));

		return orderedIds.stream()
				.map(articles::get)
				.filter(article -> article != null)
				.map(article -> new RecommendationDetailResponse.Article(
						article.getArticleId(),
						article.getTitle(),
						article.getOrganization().getName(),
						article.getPublishedAt().atOffset(KST),
						article.getTopicCode(),
						article.getUrl()))
				.toList();
	}
}

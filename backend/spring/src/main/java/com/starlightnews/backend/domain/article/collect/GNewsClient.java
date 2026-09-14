package com.starlightnews.backend.domain.article.collect;

import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.dto.GNewsArticlesResponse;
import com.starlightnews.backend.domain.article.exception.ArticleCollectErrorCode;
import com.starlightnews.backend.domain.article.support.GNewsArticleMapper;
import com.starlightnews.backend.global.error.BusinessException;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

/**
 * GNews top-headlines 에서 카테고리별 최신 기사를 가져온다.
 *
 * <p>search 엔드포인트는 검색어(q)가 필수라 카테고리 전체를 훑을 수 없어 top-headlines 만 사용한다.
 * 응답 중 저장할 수 없는 기사는 {@link GNewsArticleMapper} 가 걸러내므로 반환 목록은 저장 가능한 것만 담는다.
 */
@Component
public class GNewsClient {

	private static final String TOP_HEADLINES_PATH = "/top-headlines";

	private final RestClient restClient;
	private final GNewsProperties properties;

	public GNewsClient(RestClient.Builder restClientBuilder, GNewsProperties properties) {
		this.restClient = restClientBuilder.baseUrl(properties.baseUrl()).build();
		this.properties = properties;
	}

	/**
	 * 해당 카테고리의 최신 기사를 가져온다.
	 *
	 * @throws BusinessException 제공처 호출에 실패한 경우. 원인별로
	 *                           {@link ArticleCollectErrorCode} 를 구분해 던진다.
	 */
	public List<CollectedArticle> fetchTopHeadlines(String category) {
		GNewsArticlesResponse response = requestTopHeadlines(category);
		if (response == null) {
			return List.of();
		}

		return response.articles().stream()
				.map(article -> GNewsArticleMapper.toCollected(article, category))
				.flatMap(java.util.Optional::stream)
				.toList();
	}

	private GNewsArticlesResponse requestTopHeadlines(String category) {
		try {
			return restClient.get()
					.uri(uriBuilder -> uriBuilder
							.path(TOP_HEADLINES_PATH)
							.queryParam("category", category)
							.queryParam("lang", properties.lang())
							.queryParam("country", properties.country())
							.queryParam("max", properties.max())
							.queryParam("apikey", properties.apiKey())
							.build())
					.retrieve()
					.onStatus(HttpStatusCode::isError, (request, errorResponse) -> {
						throw new BusinessException(toErrorCode(errorResponse.getStatusCode()));
					})
					.body(GNewsArticlesResponse.class);
		} catch (ResourceAccessException networkFailure) {
			// 연결 실패·타임아웃. 다음 수집 주기에 다시 시도한다.
			throw new BusinessException(ArticleCollectErrorCode.NEWS_SOURCE_UNAVAILABLE);
		}
	}

	private static ArticleCollectErrorCode toErrorCode(HttpStatusCode status) {
		if (status.value() == 429) {
			return ArticleCollectErrorCode.NEWS_SOURCE_QUOTA_EXCEEDED;
		}
		if (status.value() == 401 || status.value() == 403) {
			return ArticleCollectErrorCode.NEWS_SOURCE_UNAUTHORIZED;
		}
		return ArticleCollectErrorCode.NEWS_SOURCE_UNAVAILABLE;
	}
}

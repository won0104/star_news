package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.dto.GNewsArticlesResponse;
import com.starlightnews.backend.domain.article.exception.ArticleCollectErrorCode;
import com.starlightnews.backend.domain.article.support.GNewsArticleMapper;
import com.starlightnews.backend.global.error.BusinessException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

/**
 * GNews top-headlines 에서 카테고리별 기사를 가져온다.
 *
 * <p>search 엔드포인트는 검색어(q)가 필수라 카테고리 전체를 훑을 수 없어 top-headlines 만 사용한다.
 * 지난 구간을 채울 때도 top-headlines 를 쓴다 — {@code from}·{@code to}·{@code page} 를 받으므로
 * 검색어 없이 구간을 지정할 수 있다.
 *
 * <p>응답 중 저장할 수 없는 기사는 {@link GNewsArticleMapper} 가 걸러내므로 반환 목록은 저장 가능한 것만 담는다.
 */
@Component
public class GNewsClient {

	private static final String TOP_HEADLINES_PATH = "/top-headlines";

	/** 속도 제한(429)에만 재시도한다. 대기는 retryDelay 의 1배, 2배다. */
	private static final int MAX_RATE_LIMIT_RETRIES = 2;

	private final RestClient restClient;
	private final GNewsProperties properties;
	private final Sleeper sleeper;

	@Autowired
	public GNewsClient(@Qualifier("gNewsRestClient") RestClient gNewsRestClient,
			GNewsProperties properties) {
		this(gNewsRestClient, properties, Thread::sleep);
	}

	/** 재시도 대기를 실제로 자지 않고 검증하려고 테스트에서 쓴다. */
	GNewsClient(RestClient gNewsRestClient, GNewsProperties properties, Sleeper sleeper) {
		this.restClient = gNewsRestClient;
		this.properties = properties;
		this.sleeper = sleeper;
	}

	@FunctionalInterface
	interface Sleeper {
		void sleep(Duration duration) throws InterruptedException;
	}

	/**
	 * 해당 카테고리의 최신 기사를 가져온다.
	 *
	 * @throws BusinessException 제공처 호출에 실패한 경우. 원인별로
	 *                           {@link ArticleCollectErrorCode} 를 구분해 던진다.
	 */
	public List<CollectedArticle> fetchTopHeadlines(String category) {
		return fetchTopHeadlines(category, null);
	}

	/**
	 * 해당 카테고리의 기사를 가져온다.
	 *
	 * @param window 가져올 구간과 페이지. {@code null} 이면 호출 시점의 최신 기사를 가져온다
	 * @throws BusinessException 제공처 호출에 실패한 경우
	 */
	public List<CollectedArticle> fetchTopHeadlines(String category, Window window) {
		GNewsArticlesResponse response = requestWithRetry(category, window);
		if (response == null) {
			return List.of();
		}

		return response.articles().stream()
				.map(article -> GNewsArticleMapper.toCollected(article, category))
				.flatMap(java.util.Optional::stream)
				.toList();
	}

	/**
	 * 가져올 구간과 페이지.
	 *
	 * <p>GNews 는 초 단위 ISO8601(UTC)만 받는다. 밀리초가 붙으면 형식 오류로 돌아온다.
	 *
	 * @param page 1부터 센다
	 */
	public record Window(OffsetDateTime from, OffsetDateTime to, int page) {

		private static final DateTimeFormatter GNEWS_TIME = DateTimeFormatter.ISO_INSTANT;

		String fromParam() {
			return format(from);
		}

		String toParam() {
			return format(to);
		}

		private static String format(OffsetDateTime value) {
			return GNEWS_TIME.format(value.toInstant().truncatedTo(ChronoUnit.SECONDS));
		}
	}

	/**
	 * 속도 제한(429)만 짧게 재시도한다.
	 *
	 * <p>쿼터 소진·인증 실패는 재시도해도 결과가 같아 바로 던지고, 회차를 멈출지는 호출 측이 정한다.
	 */
	private GNewsArticlesResponse requestWithRetry(String category, Window window) {
		for (int attempt = 0; ; attempt++) {
			try {
				return requestTopHeadlines(category, window);
			} catch (BusinessException failure) {
				if (failure.getErrorCode() != ArticleCollectErrorCode.NEWS_SOURCE_RATE_LIMITED
						|| attempt >= MAX_RATE_LIMIT_RETRIES) {
					throw failure;
				}
				pause(properties.retryDelay().multipliedBy(attempt + 1L));
			}
		}
	}

	private void pause(Duration duration) {
		try {
			sleeper.sleep(duration);
		} catch (InterruptedException interrupted) {
			// 종료 신호다. 인터럽트 상태를 보존하고 이번 카테고리는 실패로 끝낸다.
			Thread.currentThread().interrupt();
			throw new BusinessException(ArticleCollectErrorCode.NEWS_SOURCE_UNAVAILABLE);
		}
	}

	private GNewsArticlesResponse requestTopHeadlines(String category, Window window) {
		try {
			return restClient.get()
					.uri(uriBuilder -> {
						uriBuilder.path(TOP_HEADLINES_PATH)
								.queryParam("category", category)
								.queryParam("lang", properties.lang())
								.queryParam("country", properties.country())
								.queryParam("max", properties.max());
						if (window != null) {
							uriBuilder.queryParam("from", window.fromParam())
									.queryParam("to", window.toParam())
									.queryParam("page", window.page());
						}
						// 키는 마지막에 붙인다. 로그에 잘린 URL 이 남아도 키가 덜 노출된다.
						return uriBuilder.queryParam("apikey", properties.apiKey()).build();
					})
					.retrieve()
					.onStatus(HttpStatusCode::isError, (request, errorResponse) -> {
						throw new BusinessException(toErrorCode(errorResponse.getStatusCode()));
					})
					.body(GNewsArticlesResponse.class);
		} catch (RestClientException responseFailure) {
			// 연결·타임아웃뿐 아니라 잘못된 JSON/응답 타입도 카테고리 단위 실패로 격리한다.
			// 원본 예외 메시지에는 API 키를 포함한 요청 URL 이 들어갈 수 있어 전달하지 않는다.
			throw new BusinessException(ArticleCollectErrorCode.NEWS_SOURCE_UNAVAILABLE);
		}
	}

	private static ArticleCollectErrorCode toErrorCode(HttpStatusCode status) {
		if (status.value() == 429) {
			return ArticleCollectErrorCode.NEWS_SOURCE_RATE_LIMITED;
		}
		if (status.value() == 403) {
			return ArticleCollectErrorCode.NEWS_SOURCE_QUOTA_EXCEEDED;
		}
		if (status.value() == 401) {
			return ArticleCollectErrorCode.NEWS_SOURCE_UNAUTHORIZED;
		}
		return ArticleCollectErrorCode.NEWS_SOURCE_UNAVAILABLE;
	}
}

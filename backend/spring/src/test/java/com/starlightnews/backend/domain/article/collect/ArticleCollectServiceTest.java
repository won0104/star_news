package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.exception.ArticleCollectErrorCode;
import com.starlightnews.backend.domain.article.support.ArticleUrls;
import com.starlightnews.backend.global.enums.ContentType;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class ArticleCollectServiceTest {

	@Mock
	private GNewsClient gNewsClient;

	private static final List<String> CATEGORIES = List.of("general", "business", "sports");

	private GNewsProperties properties(String apiKey) {
		return new GNewsProperties("https://gnews.example.io/api/v4", apiKey, "ko", "kr", 10,
				CATEGORIES, Duration.ofSeconds(5), null);
	}

	private ArticleCollectService service(String apiKey) {
		return new ArticleCollectService(gNewsClient, properties(apiKey));
	}

	private CollectedArticle article(String url, String category) {
		return new CollectedArticle("제목", url, ArticleUrls.hash(url),
				LocalDateTime.of(2026, 9, 14, 14, 0), "본문", ContentType.FULL_TEXT,
				category, "연합뉴스", "www.yna.co.kr");
	}

	@Test
	void API_키가_없으면_수집하지_않는다() {
		List<CollectedArticle> result = service("").collectAll();

		assertThat(result).isEmpty();
		verifyNoInteractions(gNewsClient); // 키 없는 로컬·테스트에서 외부 호출이 나가면 안 된다
	}

	@Test
	void 설정된_카테고리를_모두_호출한다() {
		given(gNewsClient.fetchTopHeadlines(org.mockito.ArgumentMatchers.anyString()))
				.willReturn(List.of());

		service("key").collectAll();

		CATEGORIES.forEach(category -> verify(gNewsClient).fetchTopHeadlines(category));
	}

	@Test
	void 카테고리별_결과를_모아서_반환한다() {
		given(gNewsClient.fetchTopHeadlines("general"))
				.willReturn(List.of(article("https://news.example.com/1", "general")));
		given(gNewsClient.fetchTopHeadlines("business"))
				.willReturn(List.of(article("https://news.example.com/2", "business")));
		given(gNewsClient.fetchTopHeadlines("sports")).willReturn(List.of());

		List<CollectedArticle> result = service("key").collectAll();

		assertThat(result).extracting(CollectedArticle::url)
				.containsExactly("https://news.example.com/1", "https://news.example.com/2");
	}

	@Test
	void 여러_카테고리에_같은_기사가_있으면_한_번만_남긴다() {
		// 같은 기사가 general 과 business 에 동시에 올라오는 일이 흔하다.
		given(gNewsClient.fetchTopHeadlines("general"))
				.willReturn(List.of(article("https://news.example.com/1", "general")));
		given(gNewsClient.fetchTopHeadlines("business"))
				.willReturn(List.of(article("https://news.example.com/1", "business")));
		given(gNewsClient.fetchTopHeadlines("sports")).willReturn(List.of());

		List<CollectedArticle> result = service("key").collectAll();

		assertThat(result).hasSize(1);
		assertThat(result.get(0).sourceCategory()).isEqualTo("general"); // 먼저 수집된 쪽을 유지
	}

	@Test
	void 추적_파라미터만_다른_같은_기사도_한_번만_남긴다() {
		given(gNewsClient.fetchTopHeadlines("general"))
				.willReturn(List.of(article("https://news.example.com/1", "general")));
		given(gNewsClient.fetchTopHeadlines("business"))
				.willReturn(List.of(article("https://news.example.com/1?utm_source=gnews", "business")));
		given(gNewsClient.fetchTopHeadlines("sports")).willReturn(List.of());

		assertThat(service("key").collectAll()).hasSize(1);
	}

	@Test
	void 카테고리_하나가_실패해도_나머지는_계속_수집한다() {
		given(gNewsClient.fetchTopHeadlines("general"))
				.willThrow(new BusinessException(ArticleCollectErrorCode.NEWS_SOURCE_UNAVAILABLE));
		given(gNewsClient.fetchTopHeadlines("business"))
				.willReturn(List.of(article("https://news.example.com/2", "business")));
		given(gNewsClient.fetchTopHeadlines("sports")).willReturn(List.of());

		List<CollectedArticle> result = service("key").collectAll();

		assertThat(result).extracting(CollectedArticle::url)
				.containsExactly("https://news.example.com/2");
	}

	@Test
	void 쿼터가_소진되면_남은_카테고리를_호출하지_않는다() {
		given(gNewsClient.fetchTopHeadlines("general"))
				.willReturn(List.of(article("https://news.example.com/1", "general")));
		given(gNewsClient.fetchTopHeadlines("business"))
				.willThrow(new BusinessException(ArticleCollectErrorCode.NEWS_SOURCE_QUOTA_EXCEEDED));

		List<CollectedArticle> result = service("key").collectAll();

		// 이미 바닥난 쿼터로 남은 카테고리를 때려봐야 전부 실패한다.
		verify(gNewsClient, never()).fetchTopHeadlines("sports");
		assertThat(result).hasSize(1); // 쿼터 소진 전까지 모은 것은 살린다
	}
}

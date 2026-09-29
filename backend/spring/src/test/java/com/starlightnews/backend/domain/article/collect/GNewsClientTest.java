package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.exception.ArticleCollectErrorCode;
import com.starlightnews.backend.global.enums.ContentType;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.queryParam;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withServerError;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class GNewsClientTest {

	private static final String BASE_URL = "https://gnews.example.io/api/v4";

	private MockRestServiceServer server;
	private GNewsClient client;

	@BeforeEach
	void setUp() {
		RestClient.Builder builder = RestClient.builder();
		server = MockRestServiceServer.bindTo(builder).build();
		client = new GNewsClient(builder.baseUrl(BASE_URL).build(), new GNewsProperties(
				BASE_URL, "test-api-key", "ko", "kr", 10,
				List.of("business"), Duration.ofSeconds(5), null));
	}

	private ErrorCode errorCodeOf(Throwable thrown) {
		assertThat(thrown).isInstanceOf(BusinessException.class);
		return ((BusinessException) thrown).getErrorCode();
	}

	private String body(String articles) {
		return "{\"totalArticles\":1,\"articles\":[" + articles + "]}";
	}

	private String article(String title, String content) {
		return """
				{"title":"%s","description":"요약","content":"%s",
				 "url":"https://www.yna.co.kr/view/AKR1","publishedAt":"2026-09-14T05:00:00Z",
				 "source":{"name":"연합뉴스","url":"https://www.yna.co.kr"}}
				""".formatted(title, content);
	}

	@Test
	void 설정한_파라미터로_top_headlines를_호출한다() {
		server.expect(requestTo(org.hamcrest.Matchers.startsWith(BASE_URL + "/top-headlines")))
				.andExpect(queryParam("category", "business"))
				.andExpect(queryParam("lang", "ko"))
				.andExpect(queryParam("country", "kr"))
				.andExpect(queryParam("max", "10"))
				.andExpect(queryParam("apikey", "test-api-key"))
				.andRespond(withSuccess(body(article("기준금리 동결", "본문")), MediaType.APPLICATION_JSON));

		client.fetchTopHeadlines("business");

		server.verify();
	}

	@Test
	void 응답_기사를_수집_결과로_변환해_반환한다() {
		server.expect(requestTo(org.hamcrest.Matchers.containsString("/top-headlines")))
				.andRespond(withSuccess(body(article("기준금리 동결", "한국은행은 동결했다.")),
						MediaType.APPLICATION_JSON));

		List<CollectedArticle> result = client.fetchTopHeadlines("business");

		assertThat(result).hasSize(1);
		assertThat(result.get(0).title()).isEqualTo("기준금리 동결");
		assertThat(result.get(0).sourceCategory()).isEqualTo("business");
		assertThat(result.get(0).contentType()).isEqualTo(ContentType.FULL_TEXT);
	}

	@Test
	void 저장할_수_없는_기사는_걸러내고_나머지를_반환한다() {
		// 제목이 없는 기사 한 건이 섞여도 수집 전체를 버리지 않는다.
		String noTitle = """
				{"title":null,"description":null,"content":"본문",
				 "url":"https://www.yna.co.kr/view/AKR2","publishedAt":"2026-09-14T05:00:00Z",
				 "source":{"name":"연합뉴스","url":"https://www.yna.co.kr"}}
				""";
		server.expect(requestTo(org.hamcrest.Matchers.containsString("/top-headlines")))
				.andRespond(withSuccess("{\"totalArticles\":2,\"articles\":["
						+ article("정상 기사", "본문") + "," + noTitle + "]}", MediaType.APPLICATION_JSON));

		List<CollectedArticle> result = client.fetchTopHeadlines("business");

		assertThat(result).extracting(CollectedArticle::title).containsExactly("정상 기사");
	}

	@Test
	void 기사가_없으면_빈_목록이다() {
		server.expect(requestTo(org.hamcrest.Matchers.containsString("/top-headlines")))
				.andRespond(withSuccess("{\"totalArticles\":0,\"articles\":[]}",
						MediaType.APPLICATION_JSON));

		assertThat(client.fetchTopHeadlines("business")).isEmpty();
	}

	@Test
	void 쿼터를_초과하면_QUOTA_EXCEEDED() {
		server.expect(requestTo(org.hamcrest.Matchers.containsString("/top-headlines")))
				.andRespond(withStatus(HttpStatus.FORBIDDEN));

		Throwable thrown = catchThrowable(() -> client.fetchTopHeadlines("business"));

		assertThat(errorCodeOf(thrown)).isEqualTo(ArticleCollectErrorCode.NEWS_SOURCE_QUOTA_EXCEEDED);
	}

	@Test
	void 인증에_실패하면_UNAUTHORIZED() {
		server.expect(requestTo(org.hamcrest.Matchers.containsString("/top-headlines")))
				.andRespond(withStatus(HttpStatus.UNAUTHORIZED));

		Throwable thrown = catchThrowable(() -> client.fetchTopHeadlines("business"));

		assertThat(errorCodeOf(thrown)).isEqualTo(ArticleCollectErrorCode.NEWS_SOURCE_UNAUTHORIZED);
	}

	@Test
	void 제공처_5xx면_UNAVAILABLE() {
		server.expect(requestTo(org.hamcrest.Matchers.containsString("/top-headlines")))
				.andRespond(withServerError());

		Throwable thrown = catchThrowable(() -> client.fetchTopHeadlines("business"));

		assertThat(errorCodeOf(thrown)).isEqualTo(ArticleCollectErrorCode.NEWS_SOURCE_UNAVAILABLE);
	}

	@Test
	void 구간을_주면_from_to_page를_UTC_초단위로_붙인다() {
		// KST 로 준 구간이 UTC 로 바뀌어 나가야 한다. 밀리초가 붙으면 GNews 가 형식 오류로 돌려준다.
		server.expect(requestTo(org.hamcrest.Matchers.startsWith(BASE_URL + "/top-headlines")))
				.andExpect(queryParam("from", "2026-09-26T00:00:00Z"))
				.andExpect(queryParam("to", "2026-09-26T06:00:00Z"))
				.andExpect(queryParam("page", "2"))
				.andRespond(withSuccess(body(article("기준금리 동결", "본문")), MediaType.APPLICATION_JSON));

		client.fetchTopHeadlines("business", new GNewsClient.Window(
				OffsetDateTime.parse("2026-09-26T09:00:00+09:00"),
				OffsetDateTime.parse("2026-09-26T15:00:00.123+09:00"),
				2));

		server.verify();
	}

	@Test
	void 구간이_없으면_from_to_page를_붙이지_않는다() {
		// 정시 수집은 호출 시점 기준이다. 구간 파라미터가 섞이면 매시 같은 구간만 다시 긁는다.
		server.expect(requestTo(org.hamcrest.Matchers.allOf(
						org.hamcrest.Matchers.startsWith(BASE_URL + "/top-headlines"),
						org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("from=")),
						org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("to=")),
						org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("page=")))))
				.andRespond(withSuccess(body(article("기준금리 동결", "본문")), MediaType.APPLICATION_JSON));

		client.fetchTopHeadlines("business");

		server.verify();
	}
}

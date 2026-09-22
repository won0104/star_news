package com.starlightnews.backend.domain.recommendation.service;

import java.time.Duration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.global.client.FastApiClient;
import com.starlightnews.backend.global.client.FastApiProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class RecommendationRetuneClientTest {

	private static final String BASE_URL = "http://fastapi.test:8000";
	private static final String PATH = "/internal/v1/recommendations/retune";
	private static final String BODY = """
			{"data": {"cbfWeight": 0.8, "cfWeight": 0.2,
			          "ndcgAt10": 0.4123, "hitRateAt10": 0.5833, "recallAt10": 0.3912}}
			""";

	private MockRestServiceServer server;
	private RecommendationRetuneClient client;

	@BeforeEach
	void setUp() {
		RestClient.Builder builder = RestClient.builder();
		server = MockRestServiceServer.bindTo(builder).build();
		client = new RecommendationRetuneClient(builder.baseUrl(BASE_URL).build(),
				new FastApiProperties(BASE_URL, "test-key", Duration.ofMinutes(5)), new ObjectMapper());
	}

	@Test
	void 내부_인증_헤더를_붙여_본문_없이_POST_한다() {
		server.expect(requestTo(BASE_URL + PATH))
				.andExpect(method(HttpMethod.POST))
				.andExpect(header(FastApiClient.INTERNAL_API_KEY_HEADER, "test-key"))
				.andRespond(withSuccess(BODY, MediaType.APPLICATION_JSON));

		client.retune();

		server.verify();
	}

	@Test
	void 계산된_가중치와_지표를_돌려준다() {
		server.expect(requestTo(BASE_URL + PATH))
				.andRespond(withSuccess(BODY, MediaType.APPLICATION_JSON));

		assertThat(client.retune()).hasValueSatisfying(data -> {
			assertThat(data.cbfWeight()).isEqualByComparingTo("0.8");
			assertThat(data.cfWeight()).isEqualByComparingTo("0.2");
			assertThat(data.ndcgAt10()).isEqualByComparingTo("0.4123");
		});
	}

	@Test
	void 실패하면_예외가_아니라_빈_결과다() {
		// 주 1회짜리다. 한 번 걸러도 기존 가중치로 추천이 계속 돈다.
		server.expect(requestTo(BASE_URL + PATH))
				.andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));

		assertThat(client.retune()).isEmpty();
	}

	@Test
	void 응답_본문이_비어_있어도_빈_결과다() {
		server.expect(requestTo(BASE_URL + PATH))
				.andRespond(withSuccess("{}", MediaType.APPLICATION_JSON));

		assertThat(client.retune()).isEmpty();
	}
}

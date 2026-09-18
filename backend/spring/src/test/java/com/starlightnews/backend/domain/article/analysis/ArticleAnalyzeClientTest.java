package com.starlightnews.backend.domain.article.analysis;

import java.time.Duration;
import java.time.LocalDateTime;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Analyzed;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Halt;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Rejected;
import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisOutcome.Retryable;
import com.starlightnews.backend.domain.article.analysis.dto.ArticleAnalyzeRequest;
import com.starlightnews.backend.global.client.FastApiClient;
import com.starlightnews.backend.global.client.FastApiProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withException;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

/**
 * 기사 분석 요청이 FastAPI 계약대로 나가고, 응답이 다음 할 일로 나뉘는지 본다.
 *
 * <p>나가는 JSON 을 직접 확인한다. 필드 이름이 어긋나 요청이 거절되는 일을 이미 두 번 겪었다.
 */
class ArticleAnalyzeClientTest {

	private static final String BASE_URL = "http://fastapi.test:8000";
	private static final String URL = BASE_URL + "/internal/v1/articles/analyze";

	private MockRestServiceServer server;
	private RestClient.Builder builder;

	@BeforeEach
	void setUp() {
		// 운영과 같은 방식으로 날짜를 직렬화한다. 기본 ObjectMapper 는 OffsetDateTime 을 숫자로 쓴다.
		ObjectMapper objectMapper = new ObjectMapper().registerModule(new JavaTimeModule())
				.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
		builder = RestClient.builder().messageConverters(converters -> {
			converters.removeIf(MappingJackson2HttpMessageConverter.class::isInstance);
			converters.add(new MappingJackson2HttpMessageConverter(objectMapper));
		});
		server = MockRestServiceServer.bindTo(builder).build();
	}

	private ArticleAnalyzeClient client(String apiKey) {
		return new ArticleAnalyzeClient(builder.baseUrl(BASE_URL).build(),
				new FastApiProperties(BASE_URL, apiKey, Duration.ofSeconds(5)), new ObjectMapper());
	}

	private ArticleAnalyzeRequest request() {
		return ArticleAnalyzeRequest.of(930001L, "한국은행 기준금리 동결", "본문",
				940010L, "연합뉴스", LocalDateTime.of(2026, 9, 16, 9, 30));
	}

	private String success(String articleNodeId, String topic) {
		return """
				{"data": {"articleId": 930001, "articleNodeId": %s, "status": "COMPLETED",
				          "primaryTopicCode": %s, "subtopicCode": "ECONOMY_FINANCE"}}"""
				.formatted(articleNodeId == null ? "null" : "\"" + articleNodeId + "\"",
						topic == null ? "null" : "\"" + topic + "\"");
	}

	@Test
	void FastAPI_계약대로_요청을_보낸다() {
		server.expect(requestTo(URL))
				.andExpect(method(HttpMethod.POST))
				.andExpect(header(FastApiClient.INTERNAL_API_KEY_HEADER, "test-key"))
				.andExpect(jsonPath("$.articleId").value(930001))
				.andExpect(jsonPath("$.title").value("한국은행 기준금리 동결"))
				.andExpect(jsonPath("$.content").value("본문"))
				.andExpect(jsonPath("$.sourceId").value(940010))
				.andExpect(jsonPath("$.sourceName").value("연합뉴스"))
				.andRespond(withSuccess(success("node-1", "ECONOMY"), MediaType.APPLICATION_JSON));

		client("test-key").analyze(request());

		server.verify();
	}

	@Test
	void 발행_시각에_KST_오프셋을_붙여_보낸다() {
		// 오프셋이 없으면 FastAPI 가 Neo4j 에 LocalDateTime 으로 저장한다. Spring 그래프 조회는 이 값을
		// ZonedDateTime 으로 읽으므로 분석된 기사가 관련 기사 조회에서 깨진다.
		server.expect(requestTo(URL))
				.andExpect(jsonPath("$.publishedAt").value("2026-09-16T09:30:00+09:00"))
				.andRespond(withSuccess(success("node-1", "ECONOMY"), MediaType.APPLICATION_JSON));

		client("test-key").analyze(request());

		server.verify();
	}

	@Test
	void 분석되면_결과를_돌려준다() {
		server.expect(requestTo(URL))
				.andRespond(withSuccess(success("node-1", "ECONOMY"), MediaType.APPLICATION_JSON));

		ArticleAnalysisOutcome outcome = client("test-key").analyze(request());

		assertThat(outcome).isInstanceOfSatisfying(Analyzed.class, analyzed -> {
			assertThat(analyzed.result().articleNodeId()).isEqualTo("node-1");
			assertThat(analyzed.result().primaryTopicCode()).isEqualTo("ECONOMY");
			assertThat(analyzed.result().subtopicCode()).isEqualTo("ECONOMY_FINANCE");
		});
	}

	@Test
	void 기사_내용을_거부하면_분석_대상에서_뺀다() {
		// FastAPI 가 AI 워커의 400 을 INVALID_ARTICLE 로 돌려준다. 다시 불러도 같다.
		server.expect(requestTo(URL)).andRespond(withStatus(HttpStatus.BAD_REQUEST)
				.contentType(MediaType.APPLICATION_JSON)
				.body("{\"code\":\"INVALID_ARTICLE\",\"message\":\"분석할 기사 내용이 올바르지 않습니다.\"}"));

		assertThat(client("test-key").analyze(request())).isInstanceOf(Rejected.class);
	}

	@Test
	void 요청_형식이_틀리면_버리지_않고_다시_시도한다() {
		// 422 는 우리 쪽 계약 버그다. 기사 탓이 아니므로 버리면 버그 하나로 기사가 전부 빠진다.
		server.expect(requestTo(URL)).andRespond(withStatus(HttpStatus.UNPROCESSABLE_ENTITY));

		assertThat(client("test-key").analyze(request())).isInstanceOf(Retryable.class);
	}

	@Test
	void AI_추론이_실패하면_다시_시도한다() {
		server.expect(requestTo(URL)).andRespond(withStatus(HttpStatus.BAD_GATEWAY)
				.contentType(MediaType.APPLICATION_JSON)
				.body("{\"code\":\"EXTRACTION_FAILED\",\"message\":\"AI 분석 서비스가 추론에 실패했습니다.\"}"));

		assertThat(client("test-key").analyze(request())).isInstanceOf(Retryable.class);
	}

	@Test
	void AI_가_시간_안에_끝내지_못하면_다시_시도한다() {
		server.expect(requestTo(URL)).andRespond(withStatus(HttpStatus.GATEWAY_TIMEOUT));

		assertThat(client("test-key").analyze(request())).isInstanceOf(Retryable.class);
	}

	@Test
	void AI_워커에_닿지_못하면_다시_시도한다() {
		server.expect(requestTo(URL)).andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));

		assertThat(client("test-key").analyze(request())).isInstanceOf(Retryable.class);
	}

	@Test
	void FastAPI_에_연결하지_못하면_다시_시도한다() {
		server.expect(requestTo(URL)).andRespond(withException(new java.io.IOException("연결 실패")));

		assertThat(client("test-key").analyze(request())).isInstanceOf(Retryable.class);
	}

	@Test
	void 인증에_실패하면_회차를_멈춘다() {
		// 어느 기사를 불러도 같다. 계속 부르면 시도 횟수만 올라 멀쩡한 기사가 전부 FAILED 가 된다.
		server.expect(requestTo(URL)).andRespond(withStatus(HttpStatus.UNAUTHORIZED));

		assertThat(client("test-key").analyze(request())).isInstanceOf(Halt.class);
	}

	@Test
	void 키가_없으면_부르지_않고_회차를_멈춘다() {
		assertThat(client("").analyze(request())).isInstanceOf(Halt.class);

		server.verify();
	}

	@Test
	void 성공인데_nodeId_가_없으면_반영하지_않는다() {
		// 그대로 반영하면 node_id 가 빈 COMPLETED 기사가 생긴다.
		server.expect(requestTo(URL))
				.andRespond(withSuccess(success(null, "ECONOMY"), MediaType.APPLICATION_JSON));

		assertThat(client("test-key").analyze(request())).isInstanceOf(Retryable.class);
	}

	@Test
	void 성공인데_분류가_없으면_반영하지_않는다() {
		server.expect(requestTo(URL))
				.andRespond(withSuccess(success("node-1", null), MediaType.APPLICATION_JSON));

		assertThat(client("test-key").analyze(request())).isInstanceOf(Retryable.class);
	}

	@Test
	void 성공인데_data_가_없으면_반영하지_않는다() {
		server.expect(requestTo(URL))
				.andRespond(withSuccess("{}", MediaType.APPLICATION_JSON));

		assertThat(client("test-key").analyze(request())).isInstanceOf(Retryable.class);
	}
}

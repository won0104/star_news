package com.starlightnews.backend.global.client;

import java.time.Duration;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
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
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class FastApiClientTest {

	private static final String BASE_URL = "http://fastapi.test:8000";
	private static final String PATH = "/internal/v1/articles/analyze";

	private MockRestServiceServer server;
	private RestClient.Builder builder;

	@BeforeEach
	void setUp() {
		builder = RestClient.builder();
		server = MockRestServiceServer.bindTo(builder).build();
	}

	private FastApiClient client(String apiKey) {
		return new FastApiClient(builder.baseUrl(BASE_URL).build(),
				new FastApiProperties(BASE_URL, apiKey, Duration.ofSeconds(5)),
				new ObjectMapper());
	}

	private ErrorCode errorCodeOf(Throwable thrown) {
		assertThat(thrown).isInstanceOf(BusinessException.class);
		return ((BusinessException) thrown).getErrorCode();
	}

	/** FastAPI 의 에러 응답 형식. */
	private String errorBody(String code) {
		return "{\"code\":\"%s\",\"message\":\"실패\"}".formatted(code);
	}

	@Test
	void 내부_인증_헤더를_붙여_요청한다() {
		server.expect(requestTo(BASE_URL + PATH))
				.andExpect(method(org.springframework.http.HttpMethod.POST))
				.andExpect(header(FastApiClient.INTERNAL_API_KEY_HEADER, "test-key"))
				.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
				.andRespond(withSuccess("{\"status\":\"ok\"}", MediaType.APPLICATION_JSON));

		client("test-key").post(PATH, Map.of("articleId", 1), Map.class);

		server.verify();
	}

	@Test
	void 응답_본문을_지정한_타입으로_돌려준다() {
		server.expect(requestTo(BASE_URL + PATH))
				.andRespond(withSuccess("{\"status\":\"ok\"}", MediaType.APPLICATION_JSON));

		@SuppressWarnings("unchecked")
		Map<String, Object> result = client("test-key").post(PATH, Map.of(), Map.class);

		assertThat(result).containsEntry("status", "ok");
	}

	@Test
	void API_키가_없으면_호출하지_않고_UNAUTHORIZED() {
		// 키 없이 부르면 FastAPI 가 어차피 401 로 거절한다. 네트워크를 타지 않고 같은 이유로 끊는다.
		Throwable thrown = catchThrowable(() -> client("").post(PATH, Map.of(), Map.class));

		assertThat(errorCodeOf(thrown)).isEqualTo(InternalApiErrorCode.INTERNAL_API_UNAUTHORIZED);
		server.verify(); // 요청이 나가지 않았다
	}

	@Test
	void 키가_틀려_401이면_UNAUTHORIZED() {
		server.expect(requestTo(BASE_URL + PATH))
				.andRespond(withStatus(HttpStatus.UNAUTHORIZED)
						.body("{\"detail\":\"invalid internal api key\"}")
						.contentType(MediaType.APPLICATION_JSON));

		Throwable thrown = catchThrowable(() -> client("wrong-key").post(PATH, Map.of(), Map.class));

		assertThat(errorCodeOf(thrown)).isEqualTo(InternalApiErrorCode.INTERNAL_API_UNAUTHORIZED);
	}

	@Test
	void 요청_형식이_틀려_400이면_BAD_REQUEST() {
		server.expect(requestTo(BASE_URL + PATH))
				.andRespond(withStatus(HttpStatus.BAD_REQUEST)
						.body(errorBody("INVALID_ARTICLE")).contentType(MediaType.APPLICATION_JSON));

		Throwable thrown = catchThrowable(() -> client("test-key").post(PATH, Map.of(), Map.class));

		assertThat(errorCodeOf(thrown)).isEqualTo(InternalApiErrorCode.INTERNAL_API_BAD_REQUEST);
	}

	@Test
	void 이미_최신_상태라_409면_CONFLICT() {
		// 실패가 아니라 "할 일이 없었다"에 가깝다. 다른 4xx 와 섞이면 호출자가 구분할 수 없다.
		server.expect(requestTo(BASE_URL + PATH))
				.andRespond(withStatus(HttpStatus.CONFLICT)
						.body(errorBody("STALE_USER_GRAPH_SNAPSHOT")).contentType(MediaType.APPLICATION_JSON));

		Throwable thrown = catchThrowable(() -> client("test-key").post(PATH, Map.of(), Map.class));

		assertThat(errorCodeOf(thrown)).isEqualTo(InternalApiErrorCode.INTERNAL_API_CONFLICT);
	}

	@Test
	void Neo4j_장애로_503이면_UNAVAILABLE() {
		// 다음 주기에 다시 시도하면 되는 종류다.
		server.expect(requestTo(BASE_URL + PATH))
				.andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE)
						.body(errorBody("NEO4J_UNAVAILABLE")).contentType(MediaType.APPLICATION_JSON));

		Throwable thrown = catchThrowable(() -> client("test-key").post(PATH, Map.of(), Map.class));

		assertThat(errorCodeOf(thrown)).isEqualTo(InternalApiErrorCode.INTERNAL_API_UNAVAILABLE);
	}

	@Test
	void 분석_실패로_500이면_FAILED() {
		server.expect(requestTo(BASE_URL + PATH))
				.andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR)
						.body(errorBody("EXTRACTION_FAILED")).contentType(MediaType.APPLICATION_JSON));

		Throwable thrown = catchThrowable(() -> client("test-key").post(PATH, Map.of(), Map.class));

		assertThat(errorCodeOf(thrown)).isEqualTo(InternalApiErrorCode.INTERNAL_API_FAILED);
	}

	@Test
	void isReachable은_헬스체크가_성공하면_true다() {
		// /health 는 /internal/v1 아래가 아니라 루트에 있고 인증이 없다.
		server.expect(requestTo(BASE_URL + "/health"))
				.andRespond(withSuccess("{\"status\":\"ok\"}", MediaType.APPLICATION_JSON));

		assertThat(client("test-key").isReachable()).isTrue();
		server.verify();
	}

	@Test
	void isReachable은_실패해도_예외를_던지지_않고_false다() {
		server.expect(requestTo(BASE_URL + "/health"))
				.andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));

		assertThat(client("test-key").isReachable()).isFalse();
	}

	@Test
	void isReachable은_API_키가_없어도_확인한다() {
		// 헬스체크는 인증이 필요 없어 키 없이도 연결 여부를 알 수 있다.
		server.expect(requestTo(BASE_URL + "/health"))
				.andRespond(withSuccess("{\"status\":\"ok\"}", MediaType.APPLICATION_JSON));

		assertThat(client("").isReachable()).isTrue();
	}

	@Test
	void 본문이_비어도_상태_코드로_판단한다() {
		server.expect(requestTo(BASE_URL + PATH))
				.andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));

		Throwable thrown = catchThrowable(() -> client("test-key").post(PATH, Map.of(), Map.class));

		assertThat(errorCodeOf(thrown)).isEqualTo(InternalApiErrorCode.INTERNAL_API_FAILED);
	}
}

package com.starlightnews.backend.global.client;

import java.time.Duration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withException;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class GmsClientTest {

	private static final String BASE_URL = "https://gms.test/gmsapi/api.openai.com/v1";
	private static final String PATH = BASE_URL + "/chat/completions";

	private MockRestServiceServer server;
	private RestClient.Builder builder;

	@BeforeEach
	void setUp() {
		builder = RestClient.builder();
		server = MockRestServiceServer.bindTo(builder).build();
	}

	private GmsClient client(String apiKey) {
		return new GmsClient(builder.baseUrl(BASE_URL).build(),
				new GmsProperties(BASE_URL, apiKey, "gpt-5.4-nano", Duration.ofSeconds(5)),
				new ObjectMapper());
	}

	/** OpenAI Chat Completions 성공 응답 형식. */
	private String completion(String content) {
		return "{\"choices\":[{\"index\":0,\"finish_reason\":\"stop\","
				+ "\"message\":{\"role\":\"assistant\",\"content\":\"%s\"}}]}".formatted(content);
	}

	private ErrorCode errorCodeOf(Throwable thrown) {
		assertThat(thrown).isInstanceOf(BusinessException.class);
		return ((BusinessException) thrown).getErrorCode();
	}

	@Test
	void 지시와_입력을_역할에_나눠_보낸다() {
		server.expect(requestTo(PATH))
				.andExpect(method(HttpMethod.POST))
				.andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer test-key"))
				.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
				.andExpect(jsonPath("$.model").value("gpt-5.4-nano"))
				.andExpect(jsonPath("$.messages[0].role").value("developer"))
				.andExpect(jsonPath("$.messages[0].content").value("한국어로 답하라"))
				.andExpect(jsonPath("$.messages[1].role").value("user"))
				.andExpect(jsonPath("$.messages[1].content").value("기준금리를 요약하라"))
				.andRespond(withSuccess(completion("금통위가 동결했다."), MediaType.APPLICATION_JSON));

		client("test-key").generate("한국어로 답하라", "기준금리를 요약하라");

		server.verify();
	}

	@Test
	void 생성된_텍스트를_돌려준다() {
		server.expect(requestTo(PATH))
				.andRespond(withSuccess(completion("금통위가 동결했다."), MediaType.APPLICATION_JSON));

		assertThat(client("test-key").generate("지시", "입력")).isEqualTo("금통위가 동결했다.");
	}

	@Test
	void 앞뒤_공백은_지운다() {
		server.expect(requestTo(PATH))
				.andRespond(withSuccess(completion("\\n  금통위가 동결했다.  "), MediaType.APPLICATION_JSON));

		assertThat(client("test-key").generate("지시", "입력")).isEqualTo("금통위가 동결했다.");
	}

	@Test
	void 키가_없으면_부르지_않는다() {
		// 키 없이 부르면 401 로 거절당한다. 굳이 호출하지 않고 같은 이유로 끊는다.
		Throwable thrown = catchThrowable(() -> client("").generate("지시", "입력"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GmsErrorCode.GMS_UNAUTHORIZED);
		server.verify();
	}

	@Test
	void 인증_실패는_다시_걸_수_없는_실패로_구분한다() {
		server.expect(requestTo(PATH)).andRespond(withStatus(HttpStatus.UNAUTHORIZED)
				.contentType(MediaType.APPLICATION_JSON)
				.body("{\"error\":{\"message\":\"Invalid API key\"}}"));

		Throwable thrown = catchThrowable(() -> client("bad-key").generate("지시", "입력"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GmsErrorCode.GMS_UNAUTHORIZED);
	}

	@Test
	void 한도_초과는_따로_구분한다() {
		// 잠시 뒤 다시 걸면 되는 실패라 다른 4xx 와 뭉뚱그리지 않는다.
		server.expect(requestTo(PATH)).andRespond(withStatus(HttpStatus.TOO_MANY_REQUESTS));

		Throwable thrown = catchThrowable(() -> client("test-key").generate("지시", "입력"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GmsErrorCode.GMS_RATE_LIMITED);
	}

	@Test
	void 서버_오류는_연결_불가로_본다() {
		server.expect(requestTo(PATH)).andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));

		Throwable thrown = catchThrowable(() -> client("test-key").generate("지시", "입력"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GmsErrorCode.GMS_UNAVAILABLE);
	}

	@Test
	void 그_밖의_4xx는_일반_실패다() {
		server.expect(requestTo(PATH)).andRespond(withStatus(HttpStatus.BAD_REQUEST));

		Throwable thrown = catchThrowable(() -> client("test-key").generate("지시", "입력"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GmsErrorCode.GMS_FAILED);
	}

	@Test
	void 연결하지_못하면_연결_불가다() {
		server.expect(requestTo(PATH)).andRespond(withException(new java.io.IOException("연결 실패")));

		Throwable thrown = catchThrowable(() -> client("test-key").generate("지시", "입력"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GmsErrorCode.GMS_UNAVAILABLE);
	}

	@Test
	void 내용이_비어_있으면_빈_응답으로_본다() {
		server.expect(requestTo(PATH))
				.andRespond(withSuccess(completion("   "), MediaType.APPLICATION_JSON));

		Throwable thrown = catchThrowable(() -> client("test-key").generate("지시", "입력"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GmsErrorCode.GMS_EMPTY_RESPONSE);
	}

	@Test
	void choices가_없어도_빈_응답으로_본다() {
		server.expect(requestTo(PATH))
				.andRespond(withSuccess("{\"choices\":[]}", MediaType.APPLICATION_JSON));

		Throwable thrown = catchThrowable(() -> client("test-key").generate("지시", "입력"));

		assertThat(errorCodeOf(thrown)).isEqualTo(GmsErrorCode.GMS_EMPTY_RESPONSE);
	}

	@Test
	void 재시도하지_않는다() {
		// 다시 걸지 말지는 부르는 쪽이 정한다. 요약을 쓰는 두 곳이 필요한 정책이 다르다.
		server.expect(requestTo(PATH)).andRespond(withStatus(HttpStatus.TOO_MANY_REQUESTS));

		catchThrowable(() -> client("test-key").generate("지시", "입력"));

		server.verify();
	}
}

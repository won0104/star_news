package com.starlightnews.backend.global.alert;

import java.time.Duration;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class AlertNotifierTest {

	private static final String WEBHOOK = "https://hooks.example.com/services/T000/B000/secret-token";

	private final RestClient.Builder builder = RestClient.builder();
	private final MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();

	private AlertNotifier notifier(String webhookUrl) {
		return new AlertNotifier(builder.build(), new AlertProperties(webhookUrl, Duration.ofSeconds(3)));
	}

	@Test
	void Slack_Mattermost_가_받는_text_한_필드로_보낸다() {
		server.expect(requestTo(WEBHOOK))
				.andExpect(method(HttpMethod.POST))
				.andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
				.andExpect(jsonPath("$.text").value("[starlight-news] 기사 분석 회차 중단"))
				.andRespond(withSuccess());

		notifier(WEBHOOK).send("기사 분석 회차 중단");

		server.verify();
	}

	@Test
	void 웹훅이_없으면_아무것도_보내지_않는다() {
		notifier("").send("기사 분석 회차 중단");
		notifier(null).send("기사 분석 회차 중단");

		server.verify();
	}

	@Test
	void 웹훅이_거절해도_예외를_올리지_않는다() {
		// 알림 실패 때문에 배치가 죽으면 안 된다.
		server.expect(requestTo(WEBHOOK)).andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));

		assertThatCode(() -> notifier(WEBHOOK).send("알림")).doesNotThrowAnyException();
	}

	@Test
	void 웹훅에_닿지_못해도_예외를_올리지_않는다() {
		server.expect(requestTo(WEBHOOK)).andRespond(request -> {
			throw new java.net.SocketTimeoutException("Read timed out");
		});

		assertThatCode(() -> notifier(WEBHOOK).send("알림")).doesNotThrowAnyException();
	}
}

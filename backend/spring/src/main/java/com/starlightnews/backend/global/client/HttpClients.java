package com.starlightnews.backend.global.client;

import java.time.Duration;

import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

/**
 * 외부·내부 HTTP 호출용 RestClient 생성.
 *
 * <p>타임아웃을 반드시 지정한다. 기본값은 무제한이라, 상대가 응답하지 않으면 호출 스레드가 그대로 묶인다.
 * 스케줄러에서 부르는 호출이 묶이면 그 회차가 끝나지 않고 다음 회차까지 밀린다.
 */
public final class HttpClients {

	private HttpClients() {
	}

	/** baseUrl 과 타임아웃을 적용한 RestClient 를 만든다. */
	public static RestClient create(RestClient.Builder builder, String baseUrl, Duration timeout) {
		SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
		requestFactory.setConnectTimeout((int) timeout.toMillis());
		requestFactory.setReadTimeout((int) timeout.toMillis());

		return builder.baseUrl(baseUrl)
				.requestFactory(requestFactory)
				.build();
	}
}

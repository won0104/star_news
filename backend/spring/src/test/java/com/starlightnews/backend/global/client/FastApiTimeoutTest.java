package com.starlightnews.backend.global.client;

import java.io.IOException;
import java.net.SocketTimeoutException;

import org.junit.jupiter.api.Test;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientException;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 시간 초과를 다른 호출 실패와 가려내는지 본다.
 *
 * <p>로그에서 구분되지 않으면 기다릴 시간을 늘려야 할 일인지, 응답 형식을 고쳐야 할 일인지 알 수 없다.
 */
class FastApiTimeoutTest {

	@Test
	void 연결_단계에서_끊긴_시간_초과를_알아본다() {
		RestClientException failure = new ResourceAccessException("I/O error",
				new SocketTimeoutException("Read timed out"));

		assertThat(FastApiClient.isTimeout(failure)).isTrue();
	}

	@Test
	void 본문을_읽다_끊긴_시간_초과도_알아본다() {
		// 헤더를 받은 뒤 끊기면 응답 변환 실패로 감싸여 온다. 겉만 보면 형식 오류와 구분되지 않는다.
		RestClientException failure = new RestClientException(
				"Error while extracting response for type [X] and content type [application/octet-stream]",
				new IOException("stream closed", new SocketTimeoutException("Read timed out")));

		assertThat(FastApiClient.isTimeout(failure)).isTrue();
	}

	@Test
	void 응답_형식_오류는_시간_초과가_아니다() {
		RestClientException failure = new RestClientException("No converter for type [X]");

		assertThat(FastApiClient.isTimeout(failure)).isFalse();
	}

	@Test
	void 연결_거부는_시간_초과가_아니다() {
		RestClientException failure = new ResourceAccessException("I/O error",
				new java.net.ConnectException("Connection refused"));

		assertThat(FastApiClient.isTimeout(failure)).isFalse();
	}
}

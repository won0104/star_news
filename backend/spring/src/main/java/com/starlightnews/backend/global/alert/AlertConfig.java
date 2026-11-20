package com.starlightnews.backend.global.alert;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

/**
 * 운영 알림 웹훅 호출 설정.
 *
 * <p>RestClient 를 여기서 만들어 주입한다. 다른 내부 클라이언트와 같은 이유로, 테스트에서
 * MockRestServiceServer 를 끼울 수 있게 하기 위해서다. 웹훅 주소 전체를 요청마다 넘기므로 baseUrl 은 두지
 * 않는다.
 */
@Configuration
@EnableConfigurationProperties(AlertProperties.class)
public class AlertConfig {

	@Bean
	public RestClient alertWebhookRestClient(RestClient.Builder builder, AlertProperties properties) {
		SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
		requestFactory.setConnectTimeout((int) properties.timeout().toMillis());
		requestFactory.setReadTimeout((int) properties.timeout().toMillis());
		return builder.requestFactory(requestFactory).build();
	}
}

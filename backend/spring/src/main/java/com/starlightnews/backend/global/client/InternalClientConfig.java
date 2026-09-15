package com.starlightnews.backend.global.client;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

/**
 * 내부 API 호출 설정 등록.
 *
 * <p>RestClient 를 여기서 만들어 주입한다. 클라이언트가 직접 Builder 에 requestFactory 를 지정하면
 * 테스트에서 MockRestServiceServer 가 걸어둔 요청 가로채기가 덮어써져 실제 네트워크를 타게 된다.
 */
@Configuration
@EnableConfigurationProperties(FastApiProperties.class)
public class InternalClientConfig {

	@Bean
	public RestClient fastApiRestClient(RestClient.Builder builder, FastApiProperties properties) {
		return HttpClients.create(builder, properties.baseUrl(), properties.timeout());
	}
}

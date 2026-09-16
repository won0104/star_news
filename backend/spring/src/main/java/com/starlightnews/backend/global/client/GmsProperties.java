package com.starlightnews.backend.global.client;

import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * GMS(SSAFY 가 중계하는 OpenAI Chat Completions) 호출 설정.
 *
 * @param baseUrl 중계 서버 주소. 경로는 OpenAI 규격을 그대로 따른다
 * @param apiKey  Bearer 토큰. 커밋 금지이며 환경변수로 주입한다
 * @param model   사용할 모델 이름
 * @param timeout 한 번 호출에 허용하는 시간
 */
@ConfigurationProperties(prefix = "app.gms")
public record GmsProperties(
		String baseUrl,
		String apiKey,
		String model,
		Duration timeout
) {

	/**
	 * 키가 있어야 부를 수 있다.
	 *
	 * <p>키 없이 부르면 401 로 거절당한다. 호출하기 전에 이 값으로 걸러 로그에 이유를 남긴다.
	 */
	public boolean isConfigured() {
		return apiKey != null && !apiKey.isBlank();
	}
}

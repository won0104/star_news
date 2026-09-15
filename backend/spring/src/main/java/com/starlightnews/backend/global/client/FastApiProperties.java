package com.starlightnews.backend.global.client;

import java.time.Duration;

import jakarta.validation.constraints.NotBlank;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * FastAPI 내부 API 호출 설정.
 *
 * <p>apiKey 는 FastAPI 의 INTERNAL_API_KEY 와 같은 값이어야 한다. 값이 없으면 기동을 막지 않고
 * 호출 시점에 실패시킨다. AI 연동이 필요 없는 팀원도 앱을 띄울 수 있어야 하기 때문이다.
 */
@Validated
@ConfigurationProperties(prefix = "app.fastapi")
public record FastApiProperties(
		@NotBlank String baseUrl,
		String apiKey,
		Duration timeout
) {

	/** 기사 분석은 한 건에 1초 안팎이 걸린다. 배치가 묶이지 않도록 상한을 둔다. */
	private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(30);

	public FastApiProperties {
		timeout = timeout == null ? DEFAULT_TIMEOUT : timeout;
	}

	public boolean isConfigured() {
		return apiKey != null && !apiKey.isBlank();
	}
}

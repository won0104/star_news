package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import java.util.List;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;
import org.hibernate.validator.constraints.time.DurationMin;

/**
 * GNews 기사 수집 설정. (<a href="https://docs.gnews.io">GNews API v4</a>)
 *
 * @param categories top-headlines 의 category 값. 우리 TopicCode 로 변환하지 않고 원본 그대로 보존한다.
 * @param max        요청당 기사 수. 요금제 상한을 넘기면 GNews 가 자체적으로 줄여서 응답한다.
 */
@Validated
@ConfigurationProperties(prefix = "app.gnews")
public record GNewsProperties(
		@NotBlank String baseUrl,
		String apiKey,
		@NotBlank String lang,
		@NotBlank String country,
		@Min(1) @Max(100) int max,
		@NotEmpty List<@NotBlank String> categories,
		@DurationMin(millis = 1) Duration timeout,
		@DurationMin(millis = 100) Duration retryDelay
) {

	private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(10);
	private static final Duration DEFAULT_RETRY_DELAY = Duration.ofSeconds(1);

	public GNewsProperties {
		categories = categories == null ? List.of() : List.copyOf(categories);
		timeout = timeout == null ? DEFAULT_TIMEOUT : timeout;
		retryDelay = retryDelay == null ? DEFAULT_RETRY_DELAY : retryDelay;
	}

	/**
	 * API 키가 주입됐는지. 키를 필수로 검증해 기동을 막지는 않는다.
	 * 수집이 필요 없는 팀원도 앱을 띄울 수 있어야 해서, 키가 없으면 수집만 건너뛴다.
	 */
	public boolean isConfigured() {
		return apiKey != null && !apiKey.isBlank();
	}
}

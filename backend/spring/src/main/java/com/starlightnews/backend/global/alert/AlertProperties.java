package com.starlightnews.backend.global.alert;

import java.time.Duration;

import jakarta.validation.constraints.Pattern;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * 운영 알림 설정.
 *
 * @param webhookUrl Slack·Mattermost 수신 웹훅 주소. 비우면 로그로만 남긴다. 주소 자체가 비밀(토큰)이라
 *                   환경변수로만 주입하고 로그에 남기지 않는다
 * @param timeout    웹훅 연결·응답을 기다리는 시간. 알림 때문에 배치가 붙잡히면 안 되므로 짧게 둔다
 */
@Validated
@ConfigurationProperties(prefix = "app.alert")
public record AlertProperties(
		@Pattern(regexp = "^$|^https?://\\S+$", message = "웹훅 주소는 http(s):// 로 시작해야 합니다")
		String webhookUrl,
		Duration timeout
) {

	private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(3);

	public AlertProperties {
		timeout = timeout == null ? DEFAULT_TIMEOUT : timeout;
	}

	public boolean isConfigured() {
		return webhookUrl != null && !webhookUrl.isBlank();
	}
}

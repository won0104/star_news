package com.starlightnews.backend.global.alert;

import java.net.URI;
import java.util.Map;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

/**
 * 배치 이상을 운영자에게 알린다.
 *
 * <p>실행 기록은 DB 에 남지만 아무도 들여다보지 않으면 장애가 며칠씩 묻힌다. 사람이 손대야 하는 일
 * (회차 중단, AI 장애 차단, 추천 묶음 실패, 대사 어긋남)만 골라 웹훅으로 보낸다.
 *
 * <p>본문은 Slack·Mattermost 수신 웹훅이 함께 받는 {@code {"text": ...}} 하나다.
 *
 * <p><b>알림이 배치를 망치면 안 된다.</b> 웹훅이 느리거나 죽어도 짧은 타임아웃 뒤 로그만 남기고 돌아간다.
 * 예외는 올리지 않는다.
 *
 * <p><b>비밀을 흘리지 않는다.</b> 웹훅 주소에는 토큰이 들어 있는데, 호출 실패 예외의 메시지에 주소가
 * 그대로 실린다. 그래서 실패는 예외 종류와 상태 코드만 남긴다. 알림 문구에도 건수·상태·예외 종류만 넣고
 * 기사 본문이나 설정 값은 넣지 않는다(호출하는 쪽의 약속).
 */
@Slf4j
@Component
public class AlertNotifier {

	private static final String PREFIX = "[starlight-news] ";

	private final RestClient restClient;
	private final AlertProperties properties;

	public AlertNotifier(@Qualifier("alertWebhookRestClient") RestClient alertWebhookRestClient,
			AlertProperties properties) {
		this.restClient = alertWebhookRestClient;
		this.properties = properties;
	}

	/**
	 * 알린다. 웹훅이 설정돼 있지 않으면 로그로만 남긴다.
	 *
	 * @param message 사람이 읽을 한두 줄. 비밀·기사 본문을 넣지 않는다
	 */
	public void send(String message) {
		log.warn("[운영 알림] {}", message);
		if (!properties.isConfigured()) {
			return;
		}

		try {
			restClient.post()
					.uri(URI.create(properties.webhookUrl()))
					.contentType(MediaType.APPLICATION_JSON)
					.body(Map.of("text", PREFIX + message))
					.retrieve()
					.toBodilessEntity();
		} catch (RestClientResponseException rejected) {
			log.warn("운영 알림 웹훅이 거절했습니다. (status={})", rejected.getStatusCode().value());
		} catch (RuntimeException failure) {
			// 메시지에 웹훅 주소(토큰)가 실리므로 예외 종류만 남긴다.
			log.warn("운영 알림 웹훅 전송 실패 (원인={})", failure.getClass().getSimpleName());
		}
	}
}

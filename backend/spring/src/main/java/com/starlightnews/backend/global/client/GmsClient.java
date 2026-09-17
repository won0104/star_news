package com.starlightnews.backend.global.client;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.util.StreamUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

/**
 * GMS 호출 창구. 텍스트를 넣고 텍스트를 받는다.
 *
 * <p><b>무엇을 요약할지는 모른다.</b> 프롬프트와 재시도 정책은 부르는 쪽이 갖는다. 요약을 쓰는
 * 곳이 둘이고(추천 Event 요약은 배치라 느긋하게, 기사 요약은 사용자가 기다리므로 빨리 포기)
 * 필요한 정책이 서로 달라, 여기에 두면 한쪽이 손해를 본다.
 *
 * <p>SSAFY 가 중계하는 OpenAI Chat Completions 규격을 그대로 쓴다.
 */
@Slf4j
@Component
public class GmsClient {

	private static final String CHAT_COMPLETIONS_PATH = "/chat/completions";

	private final RestClient restClient;
	private final GmsProperties properties;
	private final ObjectMapper objectMapper;

	public GmsClient(@Qualifier("gmsRestClient") RestClient gmsRestClient,
			GmsProperties properties, ObjectMapper objectMapper) {
		this.restClient = gmsRestClient;
		this.properties = properties;
		this.objectMapper = objectMapper;
	}

	/**
	 * 지시와 입력을 주고 생성된 텍스트를 받는다.
	 *
	 * <p>재시도하지 않는다. 다시 걸지 말지는 부르는 쪽이 정한다.
	 *
	 * @param instruction 모델에게 주는 지시 (developer 역할)
	 * @param input       처리할 내용 (user 역할)
	 * @return 생성된 텍스트. 앞뒤 공백은 지운다
	 * @throws BusinessException 호출에 실패한 경우. 원인별로 {@link GmsErrorCode} 를 구분해 던진다
	 */
	public String generate(String instruction, String input) {
		if (!properties.isConfigured()) {
			log.warn("GMS API 키가 설정되지 않았습니다.");
			throw new BusinessException(GmsErrorCode.GMS_UNAUTHORIZED);
		}

		JsonNode response = request(Map.of(
				"model", properties.model(),
				"messages", List.of(
						Map.of("role", "developer", "content", instruction),
						Map.of("role", "user", "content", input))));

		return firstMessageContent(response);
	}

	private JsonNode request(Map<String, Object> body) {
		try {
			return restClient.post()
					.uri(CHAT_COMPLETIONS_PATH)
					.header(HttpHeaders.AUTHORIZATION, "Bearer " + properties.apiKey())
					.contentType(MediaType.APPLICATION_JSON)
					.body(body)
					.retrieve()
					.onStatus(HttpStatusCode::isError, (request, errorResponse) -> {
						throw new BusinessException(toErrorCode(errorResponse));
					})
					.body(JsonNode.class);
		} catch (RestClientException callFailure) {
			// 연결·타임아웃뿐 아니라 잘못된 JSON 응답도 여기로 온다.
			// 원본 메시지에는 Authorization 헤더가 실릴 수 있어 전달하지 않는다.
			log.warn("GMS 호출 실패 (원인={})", callFailure.getMessage());
			throw new BusinessException(GmsErrorCode.GMS_UNAVAILABLE);
		}
	}

	/** OpenAI 규격의 choices[0].message.content 를 꺼낸다. */
	private String firstMessageContent(JsonNode response) {
		if (response == null) {
			throw new BusinessException(GmsErrorCode.GMS_EMPTY_RESPONSE);
		}

		String content = response.path("choices").path(0).path("message").path("content").asText("");
		if (content.isBlank()) {
			log.warn("GMS 응답에 생성된 내용이 없습니다. (finishReason={})",
					response.path("choices").path(0).path("finish_reason").asText("없음"));
			throw new BusinessException(GmsErrorCode.GMS_EMPTY_RESPONSE);
		}
		return content.strip();
	}

	private GmsErrorCode toErrorCode(ClientHttpResponse response) {
		HttpStatusCode status = readStatus(response);
		log.warn("GMS 오류 응답 (status={}, message={})", status, readErrorMessage(response));

		if (status.value() == 401 || status.value() == 403) {
			return GmsErrorCode.GMS_UNAUTHORIZED;
		}
		if (status.value() == 429) {
			// 한도 초과다. 잠시 뒤 다시 걸면 되는 실패라 다른 4xx 와 뭉뚱그리지 않는다.
			return GmsErrorCode.GMS_RATE_LIMITED;
		}
		if (status.is5xxServerError()) {
			return GmsErrorCode.GMS_UNAVAILABLE;
		}
		return GmsErrorCode.GMS_FAILED;
	}

	private HttpStatusCode readStatus(ClientHttpResponse response) {
		try {
			return response.getStatusCode();
		} catch (IOException unreadable) {
			return HttpStatusCode.valueOf(500);
		}
	}

	/** OpenAI 는 실패를 {@code {"error": {"message": ...}}} 로 돌려준다. 읽을 수 없으면 null. */
	private String readErrorMessage(ClientHttpResponse response) {
		try {
			String body = StreamUtils.copyToString(response.getBody(), StandardCharsets.UTF_8);
			if (body.isBlank()) {
				return null;
			}
			return objectMapper.readTree(body).path("error").path("message").asText(null);
		} catch (IOException unreadable) {
			return null;
		}
	}
}

package com.starlightnews.backend.global.client;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.util.StreamUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

/**
 * FastAPI 내부 API(/internal/v1) 호출 창구.
 *
 * <p>모든 요청에 내부 서비스 인증 헤더를 붙인다. FastAPI 는 이 값이 자신의 INTERNAL_API_KEY 와
 * 정확히 일치하지 않으면 401 로 거절한다.
 *
 * <p>FastAPI 는 실패를 {@code {"code": ..., "message": ...}} 로 돌려준다. 그 code 를 로그에 남겨
 * 분석 실패(EXTRACTION_FAILED)인지 Neo4j 장애(NEO4J_UNAVAILABLE)인지 구분할 수 있게 한다.
 */
@Slf4j
@Component
public class FastApiClient {

	/** FastAPI dependencies.verify_internal_service 가 읽는 헤더. */
	public static final String INTERNAL_API_KEY_HEADER = "X-Internal-Api-Key";

	/** FastAPI 헬스체크. /internal/v1 아래가 아니라 루트에 있고 인증이 없다. */
	private static final String HEALTH_PATH = "/health";

	private final RestClient restClient;
	private final FastApiProperties properties;
	private final ObjectMapper objectMapper;

	public FastApiClient(@Qualifier("fastApiRestClient") RestClient fastApiRestClient,
			FastApiProperties properties, ObjectMapper objectMapper) {
		this.restClient = fastApiRestClient;
		this.properties = properties;
		this.objectMapper = objectMapper;
	}

	/**
	 * FastAPI 내부 API 에 POST 한다.
	 *
	 * @param path         /internal/v1 이후 경로 (예: {@code /internal/v1/articles/analyze})
	 * @throws BusinessException 호출에 실패한 경우. 원인별로 {@link InternalApiErrorCode} 를 구분해 던진다
	 */
	public <T> T post(String path, Object body, Class<T> responseType) {
		if (!properties.isConfigured()) {
			// 키 없이 부르면 FastAPI 가 401 로 거절한다. 굳이 호출하지 않고 같은 이유로 끊는다.
			log.warn("FastAPI 내부 API 키가 설정되지 않았습니다. (path={})", path);
			throw new BusinessException(InternalApiErrorCode.INTERNAL_API_UNAUTHORIZED);
		}

		try {
			return restClient.post()
					.uri(path)
					.header(INTERNAL_API_KEY_HEADER, properties.apiKey())
					.contentType(MediaType.APPLICATION_JSON)
					.body(body)
					.retrieve()
					.onStatus(HttpStatusCode::isError, (request, response) -> {
						throw new BusinessException(toErrorCode(path, response));
					})
					.body(responseType);
		} catch (RestClientException callFailure) {
			// 연결 실패·타임아웃뿐 아니라 응답을 읽지 못한 경우도 여기서 막는다. 그냥 두면 호출한
			// 배치의 회차 전체가 죽는다. 묶음 하나의 실패로 격리하려면 예외가 넘어가면 안 된다.
			log.warn("FastAPI 호출 실패 (path={}, 원인={})", path, callFailure.getMessage());
			throw new BusinessException(InternalApiErrorCode.INTERNAL_API_UNAVAILABLE);
		}
	}

	/**
	 * FastAPI 가 응답하는지 확인한다. 인증이 필요 없는 헬스체크를 부르므로 키가 없어도 확인할 수 있다.
	 *
	 * <p>상태 확인용이라 실패를 예외로 올리지 않고 false 로 돌려준다.
	 *
	 * @return 정상 응답하면 true
	 */
	public boolean isReachable() {
		try {
			restClient.get()
					.uri(HEALTH_PATH)
					.retrieve()
					.toBodilessEntity();
			return true;
		} catch (RestClientException unreachable) {
			log.warn("FastAPI 헬스체크 실패 (원인={})", unreachable.getMessage());
			return false;
		}
	}

	private InternalApiErrorCode toErrorCode(String path, ClientHttpResponse response) {
		HttpStatusCode status = readStatus(response);
		log.warn("FastAPI 오류 응답 (path={}, status={}, code={})", path, status, readErrorCode(response));

		if (status.value() == 401 || status.value() == 403) {
			return InternalApiErrorCode.INTERNAL_API_UNAUTHORIZED;
		}
		if (status.value() == 404) {
			// 그래프에 대상이 아직 없다는 뜻이다. 요청 형식이 틀린 400 과는 대응이 다르다.
			return InternalApiErrorCode.INTERNAL_API_NOT_FOUND;
		}
		if (status.value() == 409) {
			// 이미 더 최신 상태가 반영돼 있다는 뜻이다. 다른 4xx 와 뭉뚱그리면 호출자가 못 가른다.
			return InternalApiErrorCode.INTERNAL_API_CONFLICT;
		}
		if (status.value() == 503) {
			return InternalApiErrorCode.INTERNAL_API_UNAVAILABLE;
		}
		if (status.value() == 400) {
			// FastAPI 가 내용을 보고 거부한 경우다(AppException 400). 요청 형식이 틀린 경우는 FastAPI 가
			// 422 로 따로 준다.
			return InternalApiErrorCode.INTERNAL_API_REJECTED;
		}
		if (status.is4xxClientError()) {
			return InternalApiErrorCode.INTERNAL_API_BAD_REQUEST;
		}
		return InternalApiErrorCode.INTERNAL_API_FAILED;
	}

	private HttpStatusCode readStatus(ClientHttpResponse response) {
		try {
			return response.getStatusCode();
		} catch (IOException unreadable) {
			return HttpStatusCode.valueOf(500);
		}
	}

	/** FastAPI 가 준 code 를 뽑는다. 읽을 수 없으면 null 을 돌려주고 상태 코드만으로 판단한다. */
	private String readErrorCode(ClientHttpResponse response) {
		try {
			String body = StreamUtils.copyToString(response.getBody(), StandardCharsets.UTF_8);
			if (body.isBlank()) {
				return null;
			}
			JsonNode node = objectMapper.readTree(body);
			// AppException 계열은 code, 인증 실패는 FastAPI 기본 형식이라 detail 로 온다.
			return node.hasNonNull("code") ? node.get("code").asText() : node.path("detail").asText(null);
		} catch (IOException unreadable) {
			return null;
		}
	}
}

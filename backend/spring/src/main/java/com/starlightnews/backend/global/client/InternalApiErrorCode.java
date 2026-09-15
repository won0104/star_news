package com.starlightnews.backend.global.client;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * Spring Boot -> FastAPI 내부 호출 오류.
 *
 * <p>대부분 사용자 요청이 아니라 스케줄러·배치 경로에서 발생한다. 설정을 고쳐야 하는 실패와
 * 다음 주기에 다시 시도하면 되는 실패를 로그에서 바로 가르려고 원인을 나눈다.
 */
public enum InternalApiErrorCode implements ErrorCode {

	/** 내부 API 키가 없거나 FastAPI 의 값과 다르다. 설정을 고치기 전에는 재시도해도 소용없다. */
	INTERNAL_API_UNAUTHORIZED(HttpStatus.SERVICE_UNAVAILABLE, "AI 서버 인증에 실패했습니다."),

	/** 요청 형식이 FastAPI 가 받는 형태와 맞지 않다. 재시도해도 같은 결과다. */
	INTERNAL_API_BAD_REQUEST(HttpStatus.SERVICE_UNAVAILABLE, "AI 서버가 요청을 거부했습니다."),

	/** FastAPI 또는 그 뒤의 Neo4j 가 일시적으로 응답하지 못한다. 다음 주기에 다시 시도한다. */
	INTERNAL_API_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "AI 서버를 호출할 수 없습니다."),

	/** FastAPI 내부 처리가 실패했다(분석 실패 등). 원인은 응답 code 로 구분한다. */
	INTERNAL_API_FAILED(HttpStatus.SERVICE_UNAVAILABLE, "AI 서버 처리에 실패했습니다.");

	private final HttpStatus status;
	private final String message;

	InternalApiErrorCode(HttpStatus status, String message) {
		this.status = status;
		this.message = message;
	}

	@Override
	public HttpStatus getStatus() {
		return status;
	}

	@Override
	public String getCode() {
		return name();
	}

	@Override
	public String getMessage() {
		return message;
	}
}

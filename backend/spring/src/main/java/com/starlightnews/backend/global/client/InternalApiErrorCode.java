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

	/**
	 * 요청 형식이 FastAPI 가 받는 형태와 맞지 않다(422 등). 재시도해도 같은 결과다.
	 */
	INTERNAL_API_BAD_REQUEST(HttpStatus.SERVICE_UNAVAILABLE, "AI 서버가 요청을 거부했습니다."),

	/**
	 * FastAPI 가 요청의 내용을 보고 처리할 수 없다고 판단했다(400). 재시도해도 같은 결과다.
	 *
	 * <p>{@link #INTERNAL_API_BAD_REQUEST} 와 반대로 대상 데이터의 문제다. 기사 분석이라면 본문이
	 * 분석할 수 없는 내용이라는 뜻이라 그 기사를 분석 대상에서 빼도 된다. 둘을 섞으면 우리 쪽 버그
	 * 하나로 멀쩡한 기사가 전부 버려진다.
	 */
	INTERNAL_API_REJECTED(HttpStatus.SERVICE_UNAVAILABLE, "AI 서버가 처리할 수 없는 내용입니다."),

	/**
	 * 보낸 것보다 최신 상태가 이미 반영돼 있다.
	 *
	 * <p>실패가 아니라 "할 일이 없었다"에 가깝다. 다른 4xx 와 섞이면 호출자가 구분할 수 없어 따로 둔다.
	 */
	INTERNAL_API_CONFLICT(HttpStatus.SERVICE_UNAVAILABLE, "AI 서버에 더 최신 상태가 반영되어 있습니다."),

	/**
	 * 요청에 실린 대상을 FastAPI 가 찾지 못했다.
	 *
	 * <p>그래프에 아직 자리가 없는 경우다. 설정 문제도 장애도 아니라서 재시도가 아니라 앞 단계
	 * (사용자 그래프 동기화·기사 분석)가 먼저 돌아야 풀린다. 잘못된 요청과 섞이면 구분할 수 없어 따로 둔다.
	 */
	INTERNAL_API_NOT_FOUND(HttpStatus.SERVICE_UNAVAILABLE, "AI 서버가 대상을 찾지 못했습니다."),

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

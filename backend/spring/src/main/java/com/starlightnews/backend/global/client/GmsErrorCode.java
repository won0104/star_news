package com.starlightnews.backend.global.client;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * GMS 호출 실패 원인.
 *
 * <p>원인을 나누는 이유는 호출자의 대응이 다르기 때문이다. 한도 초과는 잠시 뒤 다시 걸면 되고,
 * 키 문제는 다시 걸어도 소용없다.
 */
public enum GmsErrorCode implements ErrorCode {

	/** 키가 없거나 거절당했다. 다시 걸어도 같다. */
	GMS_UNAUTHORIZED(HttpStatus.INTERNAL_SERVER_ERROR, "GMS 인증에 실패했습니다."),

	/** 호출 한도를 넘었다. 잠시 뒤 다시 걸면 된다. */
	GMS_RATE_LIMITED(HttpStatus.INTERNAL_SERVER_ERROR, "GMS 호출 한도를 초과했습니다."),

	/** 응답이 없거나 5xx 다. 잠시 뒤 다시 걸면 된다. */
	GMS_UNAVAILABLE(HttpStatus.INTERNAL_SERVER_ERROR, "GMS 에 연결할 수 없습니다."),

	/** 응답은 왔는데 쓸 내용이 없다. 프롬프트나 모델 설정 문제일 수 있다. */
	GMS_EMPTY_RESPONSE(HttpStatus.INTERNAL_SERVER_ERROR, "GMS 가 빈 응답을 돌려주었습니다."),

	/** 그 밖의 실패. */
	GMS_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "GMS 호출에 실패했습니다.");

	private final HttpStatus status;
	private final String message;

	GmsErrorCode(HttpStatus status, String message) {
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

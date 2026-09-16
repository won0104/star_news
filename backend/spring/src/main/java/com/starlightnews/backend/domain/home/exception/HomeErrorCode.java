package com.starlightnews.backend.domain.home.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * 홈 데이터 조회·응답 조합 실패를 나타낸다.
 */
public enum HomeErrorCode implements ErrorCode {

	HOME_DATA_FETCH_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "홈 데이터 조회에 실패했습니다.");

	private final HttpStatus status;
	private final String message;

	HomeErrorCode(HttpStatus status, String message) {
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

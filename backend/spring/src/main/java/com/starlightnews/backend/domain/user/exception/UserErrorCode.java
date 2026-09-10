package com.starlightnews.backend.domain.user.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * user 도메인의 비즈니스 규칙 위반 에러 코드.
 */
public enum UserErrorCode implements ErrorCode {

	USER_NOT_FOUND(HttpStatus.NOT_FOUND, "사용자를 찾을 수 없습니다.");

	private final HttpStatus status;
	private final String message;

	UserErrorCode(HttpStatus status, String message) {
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

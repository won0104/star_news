package com.starlightnews.backend.domain.user.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * user 도메인의 비즈니스 규칙 위반 에러 코드.
 */
public enum UserErrorCode implements ErrorCode {

	INVALID_TOPIC(HttpStatus.BAD_REQUEST, "허용되지 않는 관심 분야 코드입니다."),
	DUPLICATED_TOPIC(HttpStatus.BAD_REQUEST, "같은 관심 분야를 중복해서 선택할 수 없습니다."),
	INVALID_CURSOR(HttpStatus.BAD_REQUEST, "커서가 유효하지 않습니다."),
	EMPTY_CHANGES(HttpStatus.BAD_REQUEST, "변경할 북마크가 없습니다."),
	DUPLICATED_ARTICLE_CHANGE(HttpStatus.BAD_REQUEST, "같은 기사의 북마크 상태를 중복해서 변경할 수 없습니다."),
	ARTICLE_NOT_FOUND(HttpStatus.NOT_FOUND, "북마크할 수 있는 기사를 찾을 수 없습니다."),
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

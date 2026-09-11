package com.starlightnews.backend.domain.user.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * 개인 지식 그래프 조회의 비즈니스 규칙 위반 에러 코드.
 * 인증 오류·일반 형식 오류는 CommonErrorCode 를 재사용한다.
 */
public enum PersonalGraphErrorCode implements ErrorCode {

	INVALID_TOPIC_CODE(HttpStatus.BAD_REQUEST, "지원하지 않는 Topic 코드입니다."),
	NODE_NOT_ACQUIRED(HttpStatus.NOT_FOUND, "개인 지식 그래프에 없는 Node 입니다.");

	private final HttpStatus status;
	private final String message;

	PersonalGraphErrorCode(HttpStatus status, String message) {
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

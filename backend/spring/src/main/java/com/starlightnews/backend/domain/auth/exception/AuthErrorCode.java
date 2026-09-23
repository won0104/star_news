package com.starlightnews.backend.domain.auth.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * auth 도메인의 비즈니스 규칙 위반 에러 코드.
 * 형식 검증 오류는 CommonErrorCode.INVALID_INPUT_VALUE + errors[] 로 응답하므로 여기 두지 않는다.
 */
public enum AuthErrorCode implements ErrorCode {

	LOGIN_ID_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 사용 중인 로그인 아이디입니다."),
	INVALID_TOPIC(HttpStatus.BAD_REQUEST, "허용되지 않는 관심 분야 코드입니다."),
	DUPLICATED_TOPIC(HttpStatus.BAD_REQUEST, "같은 관심 분야를 중복해서 선택할 수 없습니다."),
	TOPIC_SELECTION_CONFLICT(HttpStatus.BAD_REQUEST, "관심 분야와 비관심 분야에 같은 항목을 선택할 수 없습니다."),
	INVALID_CREDENTIALS(HttpStatus.UNAUTHORIZED, "아이디 또는 비밀번호가 올바르지 않습니다."),
	INVALID_REFRESH_TOKEN(HttpStatus.UNAUTHORIZED, "유효하지 않은 리프레시 토큰입니다."),
	EXPIRED_REFRESH_TOKEN(HttpStatus.UNAUTHORIZED, "만료된 리프레시 토큰입니다."),
	REFRESH_TOKEN_REUSED(HttpStatus.UNAUTHORIZED, "이미 사용된 리프레시 토큰입니다. 다시 로그인해 주세요."),
	REFRESH_SESSION_NOT_FOUND(HttpStatus.UNAUTHORIZED, "세션을 찾을 수 없습니다. 다시 로그인해 주세요."),
	USER_DELETED(HttpStatus.FORBIDDEN, "탈퇴한 회원입니다.");

	private final HttpStatus status;
	private final String message;

	AuthErrorCode(HttpStatus status, String message) {
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

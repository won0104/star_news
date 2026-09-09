package com.starlightnews.backend.global.security;

import lombok.Getter;

/**
 * JWT 검증 실패. 필터 계층에서 발생하므로 GlobalExceptionHandler 가 아닌
 * AuthenticationEntryPoint 에서 최종 응답으로 변환한다.
 */
@Getter
public class JwtValidationException extends RuntimeException {

	public enum Reason {
		INVALID,
		EXPIRED
	}

	private final Reason reason;

	public JwtValidationException(Reason reason, String message, Throwable cause) {
		super(message, cause);
		this.reason = reason;
	}
}

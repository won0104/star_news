package com.starlightnews.backend.domain.demo.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/** 시연용 기사 투입 화면의 에러 코드. */
public enum DemoErrorCode implements ErrorCode {

	DEMO_ARTICLE_NOT_STORED(HttpStatus.CONFLICT,
			"같은 본문이 다른 제목으로 이미 저장돼 있어 넣을 수 없습니다."),
	DEMO_ARTICLE_NOT_FOUND(HttpStatus.NOT_FOUND, "기사를 찾을 수 없습니다."),
	DEMO_ARTICLE_NOT_ANALYZED(HttpStatus.CONFLICT, "아직 분석되지 않은 기사입니다."),
	DEMO_ANALYSIS_FAILED(HttpStatus.BAD_GATEWAY, "기사 분석에 실패했습니다. 다시 시도해 주세요.");

	private final HttpStatus status;
	private final String message;

	DemoErrorCode(HttpStatus status, String message) {
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

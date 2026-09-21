package com.starlightnews.backend.domain.user.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/** 뉴스 리포트 원본 조회 또는 응답 조합 실패를 나타낸다. */
public enum NewsReportErrorCode implements ErrorCode {

	NEWS_REPORT_AGGREGATION_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "뉴스 리포트 조회에 실패했습니다.");

	private final HttpStatus status;
	private final String message;

	NewsReportErrorCode(HttpStatus status, String message) {
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

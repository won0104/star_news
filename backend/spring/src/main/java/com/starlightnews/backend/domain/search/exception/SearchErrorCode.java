package com.starlightnews.backend.domain.search.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * 검색 요청 검증 및 Neo4j 조회 실패를 표현하는 오류 코드.
 */
public enum SearchErrorCode implements ErrorCode {

	INVALID_REQUEST(HttpStatus.BAD_REQUEST, "검색 요청값이 올바르지 않습니다."),
	SEARCH_QUERY_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "검색 결과 조회에 실패했습니다.");

	private final HttpStatus status;
	private final String message;

	SearchErrorCode(HttpStatus status, String message) {
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

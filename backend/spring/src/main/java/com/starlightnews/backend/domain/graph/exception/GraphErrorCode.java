package com.starlightnews.backend.domain.graph.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * graph 도메인의 비즈니스 규칙 위반 에러 코드.
 * 노드 미존재(RESOURCE_NOT_FOUND)·형식 오류(INVALID_INPUT_VALUE)는 CommonErrorCode 를 재사용한다.
 */
public enum GraphErrorCode implements ErrorCode {

	INVALID_NODE_TYPE(HttpStatus.BAD_REQUEST, "지원하지 않는 그래프 Node 유형입니다."),
	GRAPH_NODE_QUERY_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "그래프 Node 조회에 실패했습니다.");

	private final HttpStatus status;
	private final String message;

	GraphErrorCode(HttpStatus status, String message) {
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

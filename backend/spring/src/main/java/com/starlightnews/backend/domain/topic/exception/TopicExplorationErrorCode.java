package com.starlightnews.backend.domain.topic.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * Topic별 탐색 요청 검증 및 데이터 조회 실패를 나타낸다.
 */
public enum TopicExplorationErrorCode implements ErrorCode {

	INVALID_TOPIC_CODE(HttpStatus.BAD_REQUEST, "지원하지 않는 Topic 코드입니다."),
	TOPIC_EXPLORATION_FETCH_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "Topic별 탐색 데이터 조회에 실패했습니다.");

	private final HttpStatus status;
	private final String message;

	TopicExplorationErrorCode(HttpStatus status, String message) {
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

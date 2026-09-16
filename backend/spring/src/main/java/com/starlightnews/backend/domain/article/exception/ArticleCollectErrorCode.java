package com.starlightnews.backend.domain.article.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/**
 * 기사 수집(외부 제공처 호출) 오류.
 * 사용자 요청이 아니라 스케줄러 경로에서 발생하며, 쿼터 소진과 일시 장애를 로그에서 바로 가리려고 원인을 나눈다.
 */
public enum ArticleCollectErrorCode implements ErrorCode {

	/** 일일 요청 한도를 넘겼다. 다음 UTC 자정까지 기다린다. */
	NEWS_SOURCE_QUOTA_EXCEEDED(HttpStatus.SERVICE_UNAVAILABLE, "기사 제공처 요청 한도를 초과했습니다."),

	/** 초당 요청 제한. 짧게 대기한 뒤 제한된 횟수만 재시도한다. */
	NEWS_SOURCE_RATE_LIMITED(HttpStatus.SERVICE_UNAVAILABLE, "기사 제공처 요청 속도 제한에 도달했습니다."),

	/** API 키가 없거나 유효하지 않다. 설정을 고치기 전에는 재시도해도 소용없다. */
	NEWS_SOURCE_UNAUTHORIZED(HttpStatus.SERVICE_UNAVAILABLE, "기사 제공처 인증에 실패했습니다."),

	/** 그 밖의 호출 실패(네트워크·타임아웃·제공처 5xx). 다음 주기에 다시 시도한다. */
	NEWS_SOURCE_UNAVAILABLE(HttpStatus.SERVICE_UNAVAILABLE, "기사 제공처를 호출할 수 없습니다.");

	private final HttpStatus status;
	private final String message;

	ArticleCollectErrorCode(HttpStatus status, String message) {
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

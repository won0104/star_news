package com.starlightnews.backend.domain.article.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/** 기사 상세 조회와 요약 생성의 비즈니스 에러 코드. */
public enum ArticleErrorCode implements ErrorCode {

	ARTICLE_NOT_FOUND(HttpStatus.NOT_FOUND, "기사를 찾을 수 없습니다."),
	ARTICLE_DETAIL_QUERY_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "기사 상세 조회에 실패했습니다."),
	ARTICLE_CONTENT_UNAVAILABLE(HttpStatus.UNPROCESSABLE_ENTITY, "요약할 기사 본문이 없습니다."),
	SUMMARY_GENERATION_FAILED(HttpStatus.BAD_GATEWAY, "기사 요약 생성에 실패했습니다."),
	SUMMARY_SAVE_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "생성한 기사 요약을 저장하지 못했습니다."),
	/** 사용자·IP 별 요약 생성(GMS 호출) 한도를 넘었다. 저장된 요약 조회는 막지 않는다. */
	SUMMARY_RATE_LIMITED(HttpStatus.TOO_MANY_REQUESTS, "요약 생성 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.");

	private final HttpStatus status;
	private final String message;

	ArticleErrorCode(HttpStatus status, String message) {
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

package com.starlightnews.backend.domain.article.exception;

import com.starlightnews.backend.global.error.ErrorCode;
import org.springframework.http.HttpStatus;

/** 기사 상세 조회와 요약 생성의 비즈니스 에러 코드. */
public enum ArticleErrorCode implements ErrorCode {

	ARTICLE_NOT_FOUND(HttpStatus.NOT_FOUND, "기사를 찾을 수 없습니다."),
	ARTICLE_DETAIL_QUERY_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "기사 상세 조회에 실패했습니다."),
	ARTICLE_CONTENT_UNAVAILABLE(HttpStatus.UNPROCESSABLE_ENTITY, "요약할 기사 본문이 없습니다."),
	SUMMARY_GENERATION_FAILED(HttpStatus.BAD_GATEWAY, "기사 요약 생성에 실패했습니다."),
	SUMMARY_SAVE_FAILED(HttpStatus.INTERNAL_SERVER_ERROR, "생성한 기사 요약을 저장하지 못했습니다.");

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

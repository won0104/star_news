package com.starlightnews.backend.global.error;

import org.springframework.http.HttpStatus;

public interface ErrorCode {

	HttpStatus getStatus();

	String getCode();

	String getMessage();
}

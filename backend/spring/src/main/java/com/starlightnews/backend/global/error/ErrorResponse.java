package com.starlightnews.backend.global.error;

import java.time.Instant;
import java.util.List;

public record ErrorResponse(
		Instant timestamp,
		int status,
		String code,
		String message,
		String path,
		List<FieldErrorResponse> errors
) {

	public ErrorResponse {
		errors = errors == null ? List.of() : List.copyOf(errors);
	}

	public static ErrorResponse of(ErrorCode errorCode, String path) {
		return of(errorCode, path, List.of());
	}

	public static ErrorResponse of(
			ErrorCode errorCode,
			String path,
			List<FieldErrorResponse> errors
	) {
		return new ErrorResponse(
				Instant.now(),
				errorCode.getStatus().value(),
				errorCode.getCode(),
				errorCode.getMessage(),
				path,
				errors
		);
	}
}

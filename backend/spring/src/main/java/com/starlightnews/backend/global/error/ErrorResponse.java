package com.starlightnews.backend.global.error;

import java.time.Instant;
import java.util.List;

public record ErrorResponse(
		Instant timestamp,
		int status,
		String code,
		String message,
		String path,
		String requestId,
		List<FieldErrorResponse> errors
) {

	public ErrorResponse {
		errors = errors == null ? List.of() : List.copyOf(errors);
	}

	public static ErrorResponse of(ErrorCode errorCode, String path, String requestId) {
		return of(errorCode, path, requestId, List.of());
	}

	public static ErrorResponse of(
			ErrorCode errorCode,
			String path,
			String requestId,
			List<FieldErrorResponse> errors
	) {
		return new ErrorResponse(
				Instant.now(),
				errorCode.getStatus().value(),
				errorCode.getCode(),
				errorCode.getMessage(),
				path,
				requestId,
				errors
		);
	}
}

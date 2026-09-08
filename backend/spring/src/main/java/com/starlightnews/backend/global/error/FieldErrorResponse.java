package com.starlightnews.backend.global.error;

public record FieldErrorResponse(
		String field,
		String message
) {
}

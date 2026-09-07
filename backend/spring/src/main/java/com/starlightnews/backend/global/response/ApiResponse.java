package com.starlightnews.backend.global.response;

public record ApiResponse<T>(
		T data,
		ResponseMeta meta
) {

	public static <T> ApiResponse<T> success(T data, String requestId) {
		return new ApiResponse<>(data, new ResponseMeta(requestId));
	}
}

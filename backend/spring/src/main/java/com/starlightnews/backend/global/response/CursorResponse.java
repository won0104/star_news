package com.starlightnews.backend.global.response;

import java.util.List;

public record CursorResponse<T>(
		List<T> items,
		boolean hasNext,
		String nextCursor
) {

	public CursorResponse {
		items = items == null ? List.of() : List.copyOf(items);
	}

	public static <T> CursorResponse<T> of(
			List<T> items,
			boolean hasNext,
			String nextCursor
	) {
		return new CursorResponse<>(items, hasNext, nextCursor);
	}
}

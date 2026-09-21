package com.starlightnews.backend.domain.search.dto;

import com.starlightnews.backend.domain.search.exception.SearchErrorCode;
import com.starlightnews.backend.global.error.BusinessException;

/**
 * 검색 Query Parameter를 검증하고 서비스 계층이 사용할 값으로 변환한다.
 * 제한값은 초기 운영 기준이며 검색량과 응답 시간을 확인한 뒤 재조정할 수 있다.
 */
public record SearchRequest(
		String query,
		String cursor,
		int size
) {

	public static final int DEFAULT_SIZE = 20;
	public static final int MAX_SIZE = 50;
	public static final int MAX_QUERY_LENGTH = 200;

	public static SearchRequest of(String rawQuery, String rawCursor, String rawSize) {
		String query = validateQuery(rawQuery);
		int size = parseSize(rawSize);
		String cursor = rawCursor == null || rawCursor.isBlank() ? null : rawCursor;
		return new SearchRequest(query, cursor, size);
	}

	private static String validateQuery(String rawQuery) {
		if (rawQuery == null || rawQuery.isBlank()) {
			throw invalidRequest();
		}

		String query = rawQuery.strip();
		if (query.codePointCount(0, query.length()) > MAX_QUERY_LENGTH) {
			throw invalidRequest();
		}
		return query;
	}

	private static int parseSize(String rawSize) {
		if (rawSize == null || rawSize.isBlank()) {
			throw invalidRequest();
		}

		try {
			int size = Integer.parseInt(rawSize);
			if (size < 1 || size > MAX_SIZE) {
				throw invalidRequest();
			}
			return size;
		} catch (NumberFormatException exception) {
			throw invalidRequest();
		}
	}

	private static BusinessException invalidRequest() {
		return new BusinessException(SearchErrorCode.INVALID_REQUEST);
	}
}

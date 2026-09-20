package com.starlightnews.backend.domain.search.support;

import java.util.List;

/**
 * 검색 문장의 완전 일치 값과 조사·어미를 정리한 Token 집합.
 */
public record NormalizedSearchQuery(
		String exactPhrase,
		List<String> tokens,
		String fingerprint,
		String fulltextQuery
) {

	public NormalizedSearchQuery {
		tokens = List.copyOf(tokens);
	}
}

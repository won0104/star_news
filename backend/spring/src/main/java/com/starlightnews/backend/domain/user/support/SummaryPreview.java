package com.starlightnews.backend.domain.user.support;

/**
 * 저장된 기사 요약을 화면 미리보기용으로 자른다. 요약이 없으면 null, 있으면 {@value #LENGTH}자까지 + "…".
 * 이 API 들은 요약을 생성하지 않으며 이미 저장된 값만 다룬다.
 */
public final class SummaryPreview {

	private static final int LENGTH = 120;

	private SummaryPreview() {
	}

	public static String truncate(String summary) {
		if (summary == null || summary.isBlank()) {
			return null;
		}
		if (summary.length() <= LENGTH) {
			return summary;
		}
		return summary.substring(0, LENGTH) + "…";
	}
}

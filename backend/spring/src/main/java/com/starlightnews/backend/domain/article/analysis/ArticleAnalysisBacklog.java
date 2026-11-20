package com.starlightnews.backend.domain.article.analysis;

/**
 * 분석 회차가 끝난 뒤 남은 대기.
 *
 * @param waiting       남은 대기 수
 * @param oldestMinutes 남은 대기 중 가장 오래 기다린 기사가 수집된 지 몇 분인지. 대기가 없으면 null
 */
record ArticleAnalysisBacklog(int waiting, Long oldestMinutes) {

	String describe() {
		if (waiting == 0) {
			return "남은 대기 없음";
		}
		return oldestMinutes == null
				? "남은 대기 %d건".formatted(waiting)
				: "남은 대기 %d건 (가장 오래 기다린 기사 %d시간 %d분)"
						.formatted(waiting, oldestMinutes / 60, oldestMinutes % 60);
	}
}

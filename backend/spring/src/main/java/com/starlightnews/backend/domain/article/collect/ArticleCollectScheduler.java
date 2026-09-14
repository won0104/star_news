package com.starlightnews.backend.domain.article.collect;

import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 주기적으로 GNews 기사를 수집한다. 기본은 매시 10분(KST)이다.
 *
 * <p>정각과 30분을 피한 이유는 다른 배치가 그 시각을 쓰기 때문이다.
 * 05:00·17:00 사용자 그래프 동기화, 05:30·17:30 추천 계산, 06:00·18:00 트렌드 집계가 있다.
 * 수집 뒤에 이어질 AI 분석이 CPU 를 점유하는데 100건 기준 적재까지 10~15분이 걸리므로,
 * 추천 계산이 시작되는 30분 전에 끝나도록 10분에 시작한다.
 *
 * <p>수집 결과를 MySQL 에 저장하는 것은 기사 저장 작업이 담당한다.
 * 여기서는 수집까지만 수행하고, 저장 경로가 붙으면 이 지점에서 이어 붙인다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ArticleCollectScheduler {

	private final ArticleCollectService articleCollectService;

	@Scheduled(cron = "${app.gnews.collect-cron:0 10 * * * *}", zone = "Asia/Seoul")
	public void collect() {
		List<CollectedArticle> collected = articleCollectService.collectAll();
		log.info("수집 회차 종료: {}건", collected.size());
	}
}

package com.starlightnews.backend.domain.article.collect;

import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.service.ArticleStoreService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 주기적으로 GNews 기사를 수집해 MySQL 에 적재한다. 기본은 매시 10분(KST)이다.
 *
 * <p>정각과 30분을 피한 이유는 다른 배치가 그 시각을 쓰기 때문이다.
 * 05:00·17:00 사용자 그래프 동기화, 05:30·17:30 추천 계산, 06:00·18:00 트렌드 집계가 있다.
 * 향후 분석 작업 시간을 확보할 수 있도록 10분에 시작한다.
 *
 * <p>현재는 MySQL 저장까지만 수행하며 analysis_status 는 PROCESSING 으로 남는다.
 * FastAPI 분석 작업은 추후 연결한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ArticleCollectScheduler {

	private final ArticleCollectService articleCollectService;
	private final CollectedArticlePreprocessor preprocessor;
	private final ArticleStoreService articleStoreService;

	@Scheduled(cron = "${app.gnews.collect-cron:0 10 * * * *}", zone = "Asia/Seoul")
	public void collect() {
		List<CollectedArticle> collected = articleCollectService.collectAll();
		List<CollectedArticle> prepared = preprocessor.process(collected);
		int newlyStored = articleStoreService.store(prepared);
		log.info("수집 회차 종료: 수집 {}건, 전처리 후 {}건, 신규 저장 {}건",
				collected.size(), prepared.size(), newlyStored);
	}
}

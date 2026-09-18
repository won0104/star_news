package com.starlightnews.backend.domain.article.analysis;

import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 매시 20분(KST)에 분석 대기 중인 기사를 AI 분석에 넘긴다.
 *
 * <p>매시 10분 수집이 끝난 뒤에 돈다. 수집은 몇 분이면 끝나므로 그 회차에 들어온 기사가 곧바로
 * 분석 대상이 된다.
 *
 * <p>회차는 시간 예산(기본 30분) 안에서 끝난다. 정각에 도는 사용자 그래프 동기화와 겹치지 않게
 * 하기 위해서다. 남은 기사는 다음 회차로 넘어간다.
 */
@Component
@RequiredArgsConstructor
public class ArticleAnalysisScheduler {

	private final ArticleAnalysisBatchService analysisBatchService;

	@Scheduled(cron = "${app.article.analysis.cron:0 20 * * * *}", zone = "Asia/Seoul")
	public void analyze() {
		analysisBatchService.analyzePending();
	}
}

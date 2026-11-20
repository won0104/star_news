package com.starlightnews.backend.domain.article.analysis;

import lombok.RequiredArgsConstructor;
import net.javacrumbs.shedlock.spring.annotation.SchedulerLock;
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

	// 시간 예산 45분 + 마지막 기사 최대 180초 + 헬스체크 = 약 49분. 이보다 짧으면 회차가 도는 중에
	// 잠금이 풀려 다른 인스턴스가 같은 기사를 또 부른다. 60분을 넘기면 잡은 인스턴스가 죽었을 때
	// 다음 회차까지 막히므로 그 사이인 55분으로 둔다. 시간 예산을 바꾸면 이 값도 함께 본다.
	@Scheduled(cron = "${app.article.analysis.cron:0 20 * * * *}", zone = "Asia/Seoul")
	@SchedulerLock(name = "article-analysis",
			lockAtMostFor = "${app.article.analysis.lock-at-most-for:55m}", lockAtLeastFor = "5m")
	public void analyze() {
		analysisBatchService.analyzePending();
	}
}

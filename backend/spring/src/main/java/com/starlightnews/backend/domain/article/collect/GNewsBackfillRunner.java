package com.starlightnews.backend.domain.article.collect;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * 기동 직후 기사 백필을 한 번 실행한다.
 *
 * <p>일회성 작업이라 관리용 HTTP 경로를 새로 열지 않았다. 외부에 노출되는 경로가 하나 늘면 인증까지
 * 함께 지켜야 하는데, 몇 번 쓰고 끄는 기능에 그만한 표면을 만들 이유가 없다. {@code .env} 로 켜고
 * 재시작했다가 끝나면 다시 끄는 쪽이 안전하다.
 *
 * <p>실패해도 기동을 막지 않는다. 백필은 곁다리 작업이고, 여기서 예외를 올려보내면 서비스 전체가
 * 안 뜬다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
@ConditionalOnProperty(name = "app.gnews.backfill.enabled", havingValue = "true")
public class GNewsBackfillRunner implements ApplicationRunner {

	private final GNewsBackfillService backfillService;

	@Override
	public void run(ApplicationArguments args) {
		try {
			backfillService.backfill();
		} catch (RuntimeException failure) {
			log.error("기사 백필이 실패했습니다. 서비스는 그대로 띄웁니다.", failure);
		}
	}
}

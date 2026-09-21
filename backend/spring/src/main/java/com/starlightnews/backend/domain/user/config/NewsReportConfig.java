package com.starlightnews.backend.domain.user.config;

import java.time.Clock;
import java.time.ZoneId;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** 뉴스 리포트의 기간 경계와 생성 시각을 동일한 KST 시계로 계산한다. */
@Configuration
public class NewsReportConfig {

	private static final ZoneId KST = ZoneId.of("Asia/Seoul");

	@Bean("newsReportClock")
	Clock newsReportClock() {
		return Clock.system(KST);
	}
}

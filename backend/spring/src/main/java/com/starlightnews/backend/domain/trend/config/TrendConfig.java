package com.starlightnews.backend.domain.trend.config;

import java.time.Clock;
import java.time.ZoneId;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 트렌드 집계에 필요한 설정 객체와 KST 기준 시계를 제공한다.
 */
@Configuration
@EnableConfigurationProperties(TrendProperties.class)
public class TrendConfig {

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");

    @Bean("trendClock")
    Clock trendClock() {
        return Clock.system(KST);
    }
}

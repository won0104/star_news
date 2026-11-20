package com.starlightnews.backend.domain.article.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/** 기사 요약 생성 횟수 제한 설정을 등록한다. */
@Configuration
@EnableConfigurationProperties(ArticleSummaryRateLimitProperties.class)
public class ArticleSummaryConfig {
}

package com.starlightnews.backend.domain.article.collect;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * 기사 수집 설정 등록.
 */
@Configuration
@EnableConfigurationProperties(GNewsProperties.class)
public class ArticleCollectConfig {
}

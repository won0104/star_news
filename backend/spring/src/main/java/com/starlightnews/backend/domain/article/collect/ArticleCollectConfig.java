package com.starlightnews.backend.domain.article.collect;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 기사 수집 설정과 스케줄링 활성화.
 *
 * <p>API 키가 없으면 스케줄은 돌되 수집을 건너뛴다({@link GNewsProperties#isConfigured()}).
 * 테스트·키 없는 로컬에서 외부 호출이 나가지 않는 이유다.
 */
@Configuration
@EnableScheduling
@EnableConfigurationProperties(GNewsProperties.class)
public class ArticleCollectConfig {
}

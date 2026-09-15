package com.starlightnews.backend.domain.recommendation;

import com.starlightnews.backend.domain.recommendation.service.RecommendationRetentionProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * 추천 저장 설정.
 */
@Configuration
@EnableConfigurationProperties(RecommendationRetentionProperties.class)
public class RecommendationConfig {
}

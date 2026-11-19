package com.starlightnews.backend.domain.article.reconcile;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(GraphReconciliationProperties.class)
public class GraphReconciliationConfig {
}

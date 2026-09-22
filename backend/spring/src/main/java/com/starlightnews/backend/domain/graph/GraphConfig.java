package com.starlightnews.backend.domain.graph;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/** 그래프 조회 설정. */
@Configuration
@EnableConfigurationProperties(GraphNeighborProperties.class)
public class GraphConfig {
}

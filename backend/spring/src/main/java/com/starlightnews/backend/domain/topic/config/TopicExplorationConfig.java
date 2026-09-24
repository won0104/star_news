package com.starlightnews.backend.domain.topic.config;

import java.time.Clock;
import java.time.ZoneId;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Topic별 탐색 집계에 필요한 설정 객체와 KST 기준 시계를 제공한다.
 */
@Configuration
@EnableConfigurationProperties(TopicExplorationProperties.class)
public class TopicExplorationConfig {

	private static final ZoneId KST = ZoneId.of("Asia/Seoul");

	@Bean("topicExplorationClock")
	Clock topicExplorationClock() {
		return Clock.system(KST);
	}
}

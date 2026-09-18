package com.starlightnews.backend.domain.article.analysis;

import com.starlightnews.backend.global.client.FastApiProperties;
import com.starlightnews.backend.global.client.HttpClients;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

/**
 * 기사 분석 호출 설정.
 *
 * <p>분석만 타임아웃을 따로 둔다. 다른 내부 호출(그래프 동기화·추천 계산)은 30초면 되지만 분석은
 * AI 추론이라 수 분이 걸릴 수 있다. 공용 타임아웃을 늘리면 다른 호출이 멈췄을 때 알아차리기까지
 * 그만큼 오래 걸린다.
 */
@Configuration
@EnableConfigurationProperties(ArticleAnalysisProperties.class)
public class ArticleAnalysisConfig {

	@Bean
	public RestClient fastApiAnalysisRestClient(RestClient.Builder builder,
			FastApiProperties fastApiProperties, ArticleAnalysisProperties analysisProperties) {
		return HttpClients.create(builder, fastApiProperties.baseUrl(), analysisProperties.timeout());
	}
}

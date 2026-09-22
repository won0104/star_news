package com.starlightnews.backend.domain.recommendation;

import com.starlightnews.backend.domain.recommendation.service.RecommendationRetuneProperties;
import com.starlightnews.backend.global.client.FastApiProperties;
import com.starlightnews.backend.global.client.HttpClients;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

/**
 * 재튜닝 호출 설정.
 *
 * <p>재튜닝만 타임아웃을 따로 둔다. 다른 내부 호출은 30초면 되지만 그리드서치는 몇 분이 걸린다.
 * 공용 타임아웃을 늘리면 다른 호출이 멈췄을 때 알아차리기까지 그만큼 오래 걸린다.
 */
@Configuration
@EnableConfigurationProperties(RecommendationRetuneProperties.class)
public class RecommendationRetuneConfig {

	@Bean
	public RestClient fastApiRetuneRestClient(RestClient.Builder builder,
			FastApiProperties fastApiProperties, RecommendationRetuneProperties retuneProperties) {
		return HttpClients.create(builder, fastApiProperties.baseUrl(), retuneProperties.timeout());
	}
}

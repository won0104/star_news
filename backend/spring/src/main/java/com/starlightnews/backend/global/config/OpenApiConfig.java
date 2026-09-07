package com.starlightnews.backend.global.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class OpenApiConfig {

	@Bean
	public OpenAPI starlightNewsOpenApi() {
		return new OpenAPI()
				.info(new Info()
						.title("별빛 뉴스 API")
						.description("별빛 뉴스 백엔드 API 명세")
						.version("v1"));
	}
}

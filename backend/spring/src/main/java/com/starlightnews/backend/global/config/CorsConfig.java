package com.starlightnews.backend.global.config;

import com.starlightnews.backend.global.request.RequestIdFilter;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(CorsProperties.class)
public class CorsConfig implements WebMvcConfigurer {

	private static final String API_PATH_PATTERN = "/api/**";
	private static final long PREFLIGHT_MAX_AGE_SECONDS = 3600L;

	private final CorsProperties corsProperties;

	public CorsConfig(CorsProperties corsProperties) {
		this.corsProperties = corsProperties;
	}

	@Override
	public void addCorsMappings(CorsRegistry registry) {
		registry.addMapping(API_PATH_PATTERN)
				.allowedOrigins(corsProperties.allowedOrigins().toArray(String[]::new))
				.allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
				.allowedHeaders("*")
				.exposedHeaders(RequestIdFilter.HEADER_NAME)
				.allowCredentials(false)
				.maxAge(PREFLIGHT_MAX_AGE_SECONDS);
	}
}

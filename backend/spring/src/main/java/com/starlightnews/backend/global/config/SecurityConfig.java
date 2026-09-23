package com.starlightnews.backend.global.config;

import java.util.List;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.security.JwtAuthenticationFilter;
import com.starlightnews.backend.global.security.JwtProperties;
import com.starlightnews.backend.global.security.JwtProvider;
import com.starlightnews.backend.global.security.RestAccessDeniedHandler;
import com.starlightnews.backend.global.security.RestAuthenticationEntryPoint;
import com.starlightnews.backend.global.security.TokenBlacklist;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

@Configuration
@EnableWebSecurity
@EnableConfigurationProperties({JwtProperties.class, CorsProperties.class})
public class SecurityConfig {

	/** 인증 없이 접근 가능한 경로. */
	private static final String[] PUBLIC_PATHS = {
			"/api/v1/auth/**",
			"/api/v1/graphs/**",
			"/v3/api-docs/**",
			"/swagger-ui/**",
			"/swagger-ui.html",
			"/actuator/health"
	};

	@Bean
	public SecurityFilterChain securityFilterChain(
			HttpSecurity http,
			JwtProvider jwtProvider,
			TokenBlacklist tokenBlacklist,
			ObjectMapper objectMapper,
			CorsConfigurationSource corsConfigurationSource
	) throws Exception {
		http
				.csrf(AbstractHttpConfigurer::disable)
				.cors(cors -> cors.configurationSource(corsConfigurationSource))
				.httpBasic(AbstractHttpConfigurer::disable)
				.formLogin(AbstractHttpConfigurer::disable)
				.sessionManagement(session ->
						session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
				.authorizeHttpRequests(auth -> auth
						.requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
						.requestMatchers(HttpMethod.POST, "/api/v1/auth/logout").authenticated()
						.requestMatchers(HttpMethod.GET, "/api/v1/home").permitAll()
						.requestMatchers(HttpMethod.GET, "/api/v1/topics").permitAll()
						.requestMatchers(HttpMethod.GET, "/api/v1/search").permitAll()
						.requestMatchers(HttpMethod.GET, "/api/v1/articles/*").permitAll()
						.requestMatchers(HttpMethod.POST, "/api/v1/articles/*/summary").permitAll()
						// 시연용 기사 투입. 로그인 없이 화면에서 바로 넣을 수 있어야 한다.
						.requestMatchers("/api/v1/demo/**").permitAll()
						.requestMatchers(PUBLIC_PATHS).permitAll()
						.anyRequest().authenticated())
				.exceptionHandling(handler -> handler
						.authenticationEntryPoint(new RestAuthenticationEntryPoint(objectMapper))
						.accessDeniedHandler(new RestAccessDeniedHandler(objectMapper)))
				.addFilterBefore(
						new JwtAuthenticationFilter(jwtProvider, tokenBlacklist),
						UsernamePasswordAuthenticationFilter.class);
		return http.build();
	}

	@Bean
	public CorsConfigurationSource corsConfigurationSource(CorsProperties corsProperties) {
		CorsConfiguration configuration = new CorsConfiguration();
		configuration.setAllowedOrigins(corsProperties.allowedOrigins());
		configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
		configuration.setAllowedHeaders(List.of("*"));
		configuration.setExposedHeaders(List.of(RequestIdFilter.HEADER_NAME));
		configuration.setAllowCredentials(true);
		configuration.setMaxAge(3600L);

		UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
		source.registerCorsConfiguration("/api/**", configuration);
		return source;
	}
}

package com.starlightnews.backend.global.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class OpenApiConfig {

	private static final String BEARER_AUTH = "bearerAuth";

	@Bean
	public OpenAPI starlightNewsOpenApi() {
		return new OpenAPI()
				.info(new Info()
						.title("별빛 뉴스 API")
						.description("""
								별빛 뉴스 백엔드 API 명세

								**Swagger 테스트 방법**
								1. `인증 > 로그인` 을 실행한다.
								2. 응답 `data.accessToken` 값을 복사한다.
								3. 우측 상단 **Authorize** 버튼을 눌러 붙여넣으면(`Bearer` 접두어 불필요) 이후 보호 API 호출 시 자동으로 헤더가 붙는다.
								4. Refresh Token 은 로그인 시 `HttpOnly` 쿠키로 저장되어 재발급/로그아웃에 자동 전송된다.""")
						.version("v1"))
				.components(new Components().addSecuritySchemes(BEARER_AUTH,
						new SecurityScheme()
								.type(SecurityScheme.Type.HTTP)
								.scheme("bearer")
								.bearerFormat("JWT")))
				.addSecurityItem(new SecurityRequirement().addList(BEARER_AUTH));
	}
}

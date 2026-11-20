package com.starlightnews.backend.global.config;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.ConfigDataApplicationContextInitializer;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.core.env.Environment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

/**
 * 운영(prod) 프로파일의 보안 관련 기본값을 실제 properties 파일에서 읽어 확인한다.
 * 환경변수를 빠뜨렸을 때 위험한 쪽(공개)이 아니라 안전한 쪽(닫힘)으로 떨어지는지가 핵심이다.
 */
class ProdProfileDefaultsTest {

	private final ApplicationContextRunner runner = new ApplicationContextRunner()
			.withInitializer(new ConfigDataApplicationContextInitializer())
			.withPropertyValues("spring.profiles.active=prod");

	@BeforeEach
	void requireNoOverrides() {
		for (String name : new String[] {"SWAGGER_ENABLED", "DEMO_ENABLED", "CLIENT_IP_HEADER"}) {
			assumeTrue(System.getenv(name) == null, name + " 환경변수가 있으면 기본값을 확인할 수 없다");
		}
	}

	@Test
	void Swagger와_OpenAPI_문서는_기본으로_꺼져_있다() {
		runner.run(context -> {
			Environment environment = context.getEnvironment();
			assertThat(environment.getProperty("springdoc.api-docs.enabled", Boolean.class)).isFalse();
			assertThat(environment.getProperty("springdoc.swagger-ui.enabled", Boolean.class)).isFalse();
		});
	}

	@Test
	void 시연_API는_기본으로_꺼져_있다() {
		runner.run(context -> assertThat(
				context.getEnvironment().getProperty("app.demo.enabled", Boolean.class)).isFalse());
	}

	@Test
	void 클라이언트_IP는_nginx가_덮어쓰는_X_Real_IP에서_읽는다() {
		runner.run(context -> assertThat(
				context.getEnvironment().getProperty("app.client-ip.header")).isEqualTo("X-Real-IP"));
	}

	@Test
	void Swagger는_SWAGGER_ENABLED로_켤_수_있다() {
		runner.withPropertyValues("SWAGGER_ENABLED=true").run(context -> {
			assertThat(context.getEnvironment().getProperty("springdoc.api-docs.enabled", Boolean.class)).isTrue();
			assertThat(context.getEnvironment().getProperty("springdoc.swagger-ui.enabled", Boolean.class)).isTrue();
		});
	}

	@Test
	void 시연_API는_DEMO_ENABLED로_켤_수_있다() {
		runner.withPropertyValues("DEMO_ENABLED=true").run(context -> assertThat(
				context.getEnvironment().getProperty("app.demo.enabled", Boolean.class)).isTrue());
	}
}

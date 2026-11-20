package com.starlightnews.backend.global.security;

import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.ConfigDataApplicationContextInitializer;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

class JwtPropertiesTest {

	private static final String VALID_SECRET = "0123456789abcdef0123456789abcdef";

	private final ApplicationContextRunner runner = new ApplicationContextRunner()
			.withUserConfiguration(Config.class)
			.withPropertyValues(
					"app.jwt.access-token-validity=3600000",
					"app.jwt.refresh-token-validity=1209600000");

	@Configuration(proxyBeanMethods = false)
	@EnableConfigurationProperties(JwtProperties.class)
	static class Config {
	}

	@Test
	void 서명_키가_32바이트이면_기동한다() {
		runner.withPropertyValues("app.jwt.secret=" + VALID_SECRET).run(context -> {
			assertThat(context).hasNotFailed();
			assertThat(context.getBean(JwtProperties.class).secret()).isEqualTo(VALID_SECRET);
		});
	}

	@Test
	void 서명_키가_비어_있으면_기동하지_않는다() {
		runner.withPropertyValues("app.jwt.secret=").run(context -> {
			assertThat(context).hasFailed();
			assertThat(context.getStartupFailure()).rootCause().hasMessageContaining("JWT_SECRET");
		});
	}

	@Test
	void 서명_키가_32바이트보다_짧으면_기동하지_않는다() {
		runner.withPropertyValues("app.jwt.secret=" + VALID_SECRET.substring(1)).run(context -> {
			assertThat(context).hasFailed();
			assertThat(context.getStartupFailure()).rootCause().hasMessageContaining("32바이트");
		});
	}

	@Test
	void 운영_프로파일은_JWT_SECRET_이_없으면_기동하지_않는다() {
		// 예전에는 기본 설정에 공개된 키가 들어 있어 JWT_SECRET 을 빠뜨려도 그 키로 떴다.
		assumeTrue(System.getenv("JWT_SECRET") == null, "JWT_SECRET 환경변수가 있으면 확인할 수 없다");

		profileRunner("prod").run(context -> {
			assertThat(context).hasFailed();
			assertThat(context.getStartupFailure()).rootCause().hasMessageContaining("JWT_SECRET");
		});
	}

	@Test
	void 로컬_프로파일은_JWT_SECRET_없이도_개발용_키로_기동한다() {
		assumeTrue(System.getenv("JWT_SECRET") == null, "JWT_SECRET 환경변수가 있으면 확인할 수 없다");

		profileRunner("local").run(context -> assertThat(context).hasNotFailed());
	}

	@Test
	void 테스트_프로파일은_전용_키로_기동한다() {
		profileRunner("test").run(context -> assertThat(context).hasNotFailed());
	}

	/** 실제 application*.properties 를 읽어 해당 프로파일로 JwtProperties 만 바인딩한다. */
	private ApplicationContextRunner profileRunner(String profile) {
		return new ApplicationContextRunner()
				.withInitializer(new ConfigDataApplicationContextInitializer())
				.withUserConfiguration(Config.class)
				.withPropertyValues("spring.profiles.active=" + profile);
	}
}

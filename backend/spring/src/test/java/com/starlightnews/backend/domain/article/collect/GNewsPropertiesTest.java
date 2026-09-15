package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;
import static org.assertj.core.api.Assertions.assertThat;

class GNewsPropertiesTest {
    private final ApplicationContextRunner runner = new ApplicationContextRunner()
        .withUserConfiguration(Config.class)
        .withPropertyValues("app.gnews.base-url=https://gnews.example.test", "app.gnews.lang=ko",
            "app.gnews.country=kr", "app.gnews.max=12", "app.gnews.categories=general,business");

    @Configuration(proxyBeanMethods = false)
    @EnableConfigurationProperties(GNewsProperties.class)
    static class Config { }

    @Test void 타임아웃과_재시도_대기의_기본값을_바인딩한다() {
        runner.run(context -> {
            assertThat(context).hasNotFailed();
            var properties = context.getBean(GNewsProperties.class);
            assertThat(properties.timeout()).isEqualTo(Duration.ofSeconds(10));
            assertThat(properties.retryDelay()).isEqualTo(Duration.ofSeconds(1));
        });
    }

    @ParameterizedTest
    @ValueSource(strings = {"retry-delay=0ms", "retry-delay=99ms", "timeout=0ms"})
    void 무제한_타임아웃과_너무_짧은_재시도_대기를_거절한다(String setting) {
        // 타임아웃 0 은 무제한이라 스케줄러 스레드가 묶인다.
        runner.withPropertyValues("app.gnews." + setting).run(context -> assertThat(context).hasFailed());
    }
}

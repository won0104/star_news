package com.starlightnews.backend.domain.auth.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/** 로그인 시도 제한 설정을 등록한다. */
@Configuration
@EnableConfigurationProperties(LoginAttemptProperties.class)
public class LoginAttemptConfig {
}

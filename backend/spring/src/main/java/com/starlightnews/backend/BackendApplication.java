package com.starlightnews.backend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.security.servlet.UserDetailsServiceAutoConfiguration;

/**
 * 인증은 JWT 필터가 처리하므로 Spring Security 의 기본 사용자 자동 설정을 끈다.
 *
 * <p>켜 두면 {@code user} 라는 인메모리 계정이 만들어지고 기동할 때마다 임의 비밀번호가 로그에 찍힌다.
 * 지금은 httpBasic·formLogin 이 꺼져 있어 그 계정으로 들어올 입구가 없지만, 나중에 누가 디버깅하려고
 * 잠깐 켜는 순간 실제 구멍이 된다.
 */
@SpringBootApplication(exclude = UserDetailsServiceAutoConfiguration.class)
public class BackendApplication {

	public static void main(String[] args) {
		SpringApplication.run(BackendApplication.class, args);
	}

}

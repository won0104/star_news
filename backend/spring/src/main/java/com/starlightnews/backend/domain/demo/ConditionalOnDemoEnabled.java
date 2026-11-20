package com.starlightnews.backend.domain.demo;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;

/**
 * 시연 기능이 켜졌을 때(app.demo.enabled=true)만 빈을 등록한다.
 *
 * <p>시연 API 는 로그인 없이 임의 기사를 저장하고, 그 자리에서 CPU 하나짜리 AI 워커에 분석을 동기로
 * 맡긴다. 운영에 늘 열어 두면 아무나 가짜 기사로 그래프를 오염시키거나 분석 요청을 몰아 워커를 묶어
 * 둘 수 있다. 그래서 기본은 꺼 두고, 발표처럼 필요할 때만 DEMO_ENABLED=true 로 켠다.
 *
 * <p>컨트롤러만 끄지 않고 서비스·저장소까지 함께 끈다. 빈이 없으면 다른 경로에서 실수로 끌어다 쓸 수도
 * 없다. 보안 설정의 permitAll 도 같은 프로퍼티({@link #PROPERTY})를 본다.
 */
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@Documented
@ConditionalOnProperty(name = ConditionalOnDemoEnabled.PROPERTY, havingValue = "true")
public @interface ConditionalOnDemoEnabled {

	/** 시연 기능 스위치 프로퍼티. */
	String PROPERTY = "app.demo.enabled";
}

package com.starlightnews.backend.global.config;

import javax.sql.DataSource;

import net.javacrumbs.shedlock.core.LockProvider;
import net.javacrumbs.shedlock.provider.jdbctemplate.JdbcTemplateLockProvider;
import net.javacrumbs.shedlock.spring.annotation.EnableSchedulerLock;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * 여러 인스턴스가 같은 배치를 동시에 돌리지 않게 잠근다.
 *
 * <p>{@code @Scheduled} 는 인스턴스마다 따로 돈다. 앱을 두 대 띄우면 수집·분석·추천이 두 번씩 돌아
 * CPU 하나뿐인 AI 워커에 요청이 두 줄로 서고, 추천 회차가 겹쳐 생기고, GNews 요청 한도를 두 배로 쓴다.
 * 배치마다 {@code @SchedulerLock} 을 달아 먼저 잡은 인스턴스만 돌게 한다.
 *
 * <p><b>잠금 시각은 DB 서버 시계로 잰다({@code usingDbTime}).</b> 인스턴스마다 시계가 조금씩 어긋나면
 * 한쪽은 잠금이 끝났다고 보고 다른 쪽은 아직이라고 봐서 같은 회차가 겹친다. DB 시각 하나로 재면 그런
 * 일이 없다. ShedLock 은 MySQL 에서 {@code UTC_TIMESTAMP(3)} 를 쓰므로 {@code shedlock} 테이블의 시각은
 * 다른 테이블(KST)과 달리 UTC 다(V18 마이그레이션 참고).
 *
 * <p>{@code defaultLockAtMostFor} 는 잠금을 잡은 인스턴스가 죽었을 때 잠금이 풀리는 시간이다.
 * 배치마다 실제 소요 시간에 맞춰 따로 정하고, 여기 값은 빠뜨린 배치를 위한 안전망이다.
 */
@Configuration(proxyBeanMethods = false)
@EnableSchedulerLock(defaultLockAtMostFor = "1h")
public class SchedulerLockConfig {

	@Bean
	public LockProvider lockProvider(DataSource dataSource) {
		return new JdbcTemplateLockProvider(JdbcTemplateLockProvider.Configuration.builder()
				.withJdbcTemplate(new JdbcTemplate(dataSource))
				.usingDbTime()
				.build());
	}
}

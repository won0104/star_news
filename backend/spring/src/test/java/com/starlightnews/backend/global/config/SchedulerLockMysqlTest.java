package com.starlightnews.backend.global.config;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

import net.javacrumbs.shedlock.core.LockConfiguration;
import net.javacrumbs.shedlock.core.LockProvider;
import net.javacrumbs.shedlock.core.SimpleLock;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * V18 의 shedlock 테이블과 DB 시각 기반 잠금이 실제 MySQL 에서 맞물리는지 확인한다.
 *
 * <p>잠금은 트랜잭션 밖에서 커밋돼야 다른 인스턴스가 본다. 그래서 {@code @Transactional} 을 달지 않고
 * 테스트마다 고유한 잠금 이름을 쓴다.
 */
@SpringBootTest
@ActiveProfiles("test")
class SchedulerLockMysqlTest {

	@Autowired
	private LockProvider lockProvider;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	private LockConfiguration config(String name, Duration atMost, Duration atLeast) {
		return new LockConfiguration(Instant.now(), name, atMost, atLeast);
	}

	@Test
	void 잡혀_있는_동안에는_같은_이름의_잠금을_또_잡지_못한다() {
		String name = "test-lock-" + System.nanoTime();

		Optional<SimpleLock> first = lockProvider.lock(config(name, Duration.ofMinutes(10), Duration.ZERO));
		Optional<SimpleLock> second = lockProvider.lock(config(name, Duration.ofMinutes(10), Duration.ZERO));

		assertThat(first).isPresent();
		assertThat(second).isEmpty();

		first.get().unlock();
		assertThat(lockProvider.lock(config(name, Duration.ofMinutes(10), Duration.ZERO))).isPresent();
	}

	@Test
	void lockAtLeastFor_동안은_풀어도_다시_잡지_못한다() {
		String name = "test-lock-" + System.nanoTime();

		lockProvider.lock(config(name, Duration.ofMinutes(10), Duration.ofMinutes(5))).orElseThrow().unlock();

		assertThat(lockProvider.lock(config(name, Duration.ofMinutes(10), Duration.ZERO))).isEmpty();
	}

	@Test
	void 잠금_시각은_DB_서버의_UTC_시각으로_찍힌다() {
		String name = "test-lock-" + System.nanoTime();
		lockProvider.lock(config(name, Duration.ofMinutes(10), Duration.ZERO)).orElseThrow();

		Long skewSeconds = jdbcTemplate.queryForObject(
				"SELECT ABS(TIMESTAMPDIFF(SECOND, locked_at, UTC_TIMESTAMP(3))) FROM shedlock WHERE name = ?",
				Long.class, name);
		assertThat(skewSeconds).isLessThan(60L);
	}
}

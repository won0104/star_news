package com.starlightnews.backend.global.ratelimit;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class InMemoryRateLimitStoreTest {

	private final MutableClock clock = new MutableClock(Instant.parse("2026-11-20T00:00:00Z"));
	private final InMemoryRateLimitStore store = new InMemoryRateLimitStore(clock);

	@Test
	void 고정_창_안에서는_횟수가_쌓이고_창이_지나면_처음부터_센다() {
		assertThat(store.incrementInWindow("k", Duration.ofMinutes(10))).isEqualTo(1);
		clock.advance(Duration.ofMinutes(9));
		assertThat(store.incrementInWindow("k", Duration.ofMinutes(10))).isEqualTo(2);

		// 창은 처음 올린 시각부터 10분이다. 두 번째로 올렸다고 늘어나지 않는다.
		clock.advance(Duration.ofMinutes(1));
		assertThat(store.count("k")).isZero();
		assertThat(store.incrementInWindow("k", Duration.ofMinutes(10))).isEqualTo(1);
	}

	@Test
	void 연장_방식은_올릴_때마다_만료를_미룬다() {
		store.incrementAndExtend("k", Duration.ofMinutes(15));
		clock.advance(Duration.ofMinutes(14));
		store.incrementAndExtend("k", Duration.ofMinutes(15));
		clock.advance(Duration.ofMinutes(14));

		assertThat(store.count("k")).isEqualTo(2);

		clock.advance(Duration.ofMinutes(1));
		assertThat(store.count("k")).isZero();
	}

	@Test
	void reset_하면_0이_된다() {
		store.incrementInWindow("k", Duration.ofMinutes(1));
		store.reset("k");

		assertThat(store.count("k")).isZero();
	}

	@Test
	void 없는_키는_0이다() {
		assertThat(store.count("missing")).isZero();
	}

	@Test
	void 만료된_키는_주기적으로_정리된다() {
		for (int i = 0; i < 1_000; i++) {
			store.incrementInWindow("ip:" + i, Duration.ofMinutes(1));
		}
		clock.advance(Duration.ofMinutes(2));
		for (int i = 0; i < 100; i++) {
			store.incrementInWindow("fresh:" + i, Duration.ofMinutes(1));
		}

		assertThat(store.size()).isLessThanOrEqualTo(100);
	}

	@Test
	void 같은_키를_동시에_올려도_횟수가_빠지지_않는다() throws Exception {
		InMemoryRateLimitStore realStore = new InMemoryRateLimitStore();
		int threads = 8;
		int perThread = 500;
		ExecutorService executor = Executors.newFixedThreadPool(threads);
		CountDownLatch start = new CountDownLatch(1);
		for (int t = 0; t < threads; t++) {
			executor.submit(() -> {
				start.await();
				for (int i = 0; i < perThread; i++) {
					realStore.incrementInWindow("k", Duration.ofMinutes(1));
				}
				return null;
			});
		}
		start.countDown();
		executor.shutdown();
		assertThat(executor.awaitTermination(10, TimeUnit.SECONDS)).isTrue();

		assertThat(realStore.count("k")).isEqualTo((long) threads * perThread);
	}

	private static final class MutableClock extends Clock {

		private Instant now;

		MutableClock(Instant now) {
			this.now = now;
		}

		void advance(Duration duration) {
			now = now.plus(duration);
		}

		@Override
		public ZoneOffset getZone() {
			return ZoneOffset.UTC;
		}

		@Override
		public Clock withZone(java.time.ZoneId zone) {
			return this;
		}

		@Override
		public Instant instant() {
			return now;
		}
	}
}

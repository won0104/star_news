package com.starlightnews.backend.global.ratelimit;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * 인메모리 횟수 저장소 (개발/단일 인스턴스용).
 * app.auth.store=redis 이면 {@link RedisRateLimitStore} 로 교체된다.
 *
 * <p>조회 시점에 만료를 확인하고(lazy expiry), 일정 횟수마다 만료된 키를 한꺼번에 지운다.
 * IP 별로 키가 생기므로 지우지 않으면 여러 IP 에서 한 번씩만 찔러도 맵이 계속 커진다.
 */
@Component
@ConditionalOnProperty(name = "app.auth.store", havingValue = "memory", matchIfMissing = true)
public class InMemoryRateLimitStore implements RateLimitStore {

	/** 이 횟수만큼 올릴 때마다 만료된 키를 정리한다. */
	private static final int SWEEP_INTERVAL = 1_024;

	private final ConcurrentHashMap<String, Counter> counters = new ConcurrentHashMap<>();
	private final AtomicLong operations = new AtomicLong();
	private final Clock clock;

	@Autowired
	public InMemoryRateLimitStore() {
		this(Clock.systemUTC());
	}

	InMemoryRateLimitStore(Clock clock) {
		this.clock = clock;
	}

	@Override
	public long incrementInWindow(String key, Duration window) {
		return increment(key, window, false);
	}

	@Override
	public long incrementAndExtend(String key, Duration ttl) {
		return increment(key, ttl, true);
	}

	@Override
	public long count(String key) {
		Counter counter = counters.get(key);
		if (counter == null) {
			return 0;
		}
		if (counter.isExpired(clock.instant())) {
			counters.remove(key, counter);
			return 0;
		}
		return counter.count();
	}

	@Override
	public void reset(String key) {
		counters.remove(key);
	}

	private long increment(String key, Duration ttl, boolean extend) {
		sweepOccasionally();
		Instant now = clock.instant();
		// compute 는 키 단위로 원자적이라 같은 키를 동시에 올려도 횟수가 빠지지 않는다.
		Counter updated = counters.compute(key, (ignored, current) -> {
			if (current == null || current.isExpired(now)) {
				return new Counter(1, now.plus(ttl));
			}
			Instant expiresAt = extend ? now.plus(ttl) : current.expiresAt();
			return new Counter(current.count() + 1, expiresAt);
		});
		return updated.count();
	}

	private void sweepOccasionally() {
		if (operations.incrementAndGet() % SWEEP_INTERVAL != 0) {
			return;
		}
		Instant now = clock.instant();
		counters.entrySet().removeIf(entry -> entry.getValue().isExpired(now));
	}

	/** 테스트용: 남아 있는 키 수. */
	int size() {
		return counters.size();
	}

	private record Counter(long count, Instant expiresAt) {

		boolean isExpired(Instant now) {
			return !now.isBefore(expiresAt);
		}
	}
}

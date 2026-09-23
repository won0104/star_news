package com.starlightnews.backend.global.security;

import java.time.Duration;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class InMemoryRefreshSessionStoreTest {

	private static final Duration TTL = Duration.ofMinutes(30);

	private InMemoryRefreshSessionStore store;

	@BeforeEach
	void setUp() {
		store = new InMemoryRefreshSessionStore();
	}

	@Test
	void 저장한_세션을_세션ID로_조회한다() {
		store.save("sid-1", new RefreshSession(42L, "hash-1"), TTL);

		Optional<RefreshSession> found = store.find("sid-1");

		assertThat(found).contains(new RefreshSession(42L, "hash-1"));
	}

	@Test
	void 없는_세션ID를_조회하면_빈_Optional이다() {
		assertThat(store.find("nope")).isEmpty();
	}

	@Test
	void TTL이_지난_세션은_조회되지_않는다() {
		store.save("sid-1", new RefreshSession(1L, "hash-1"), Duration.ofSeconds(-1));

		assertThat(store.find("sid-1")).isEmpty();
	}

	@Test
	void 삭제한_세션은_조회되지_않는다() {
		store.save("sid-1", new RefreshSession(1L, "hash-1"), TTL);

		store.delete("sid-1");

		assertThat(store.find("sid-1")).isEmpty();
	}

	@Test
	void 없는_세션을_삭제해도_예외가_없다() {
		store.delete("nope");
	}

	@Test
	void 같은_세션ID로_다시_저장하면_최신_값으로_덮어쓴다() {
		store.save("sid-1", new RefreshSession(1L, "old"), TTL);
		store.save("sid-1", new RefreshSession(1L, "new"), TTL);

		assertThat(store.find("sid-1")).contains(new RefreshSession(1L, "new"));
	}

	@Test
	void 현재_RT_해시가_맞으면_같은_세션의_해시를_교체한다() {
		store.save("sid-1", new RefreshSession(1L, "old"), TTL);

		RefreshSessionRotationResult result = store.rotate("sid-1", "old", "new", TTL);

		assertThat(result).isEqualTo(RefreshSessionRotationResult.rotated(1L));
		assertThat(store.find("sid-1")).contains(new RefreshSession(1L, "new"));
	}

	@Test
	void 이미_교체된_RT를_다시_쓰면_토큰_계열을_삭제한다() {
		store.save("sid-1", new RefreshSession(1L, "current"), TTL);

		RefreshSessionRotationResult result = store.rotate("sid-1", "old", "next", TTL);

		assertThat(result).isEqualTo(RefreshSessionRotationResult.reused());
		assertThat(store.find("sid-1")).isEmpty();
	}

	@Test
	void 없는_세션을_교체하면_NOT_FOUND를_반환한다() {
		assertThat(store.rotate("sid-1", "old", "new", TTL))
				.isEqualTo(RefreshSessionRotationResult.notFound());
	}

	@Test
	void 만료된_세션을_교체하면_NOT_FOUND를_반환하고_정리한다() {
		store.save("sid-1", new RefreshSession(1L, "old"), Duration.ofSeconds(-1));

		assertThat(store.rotate("sid-1", "old", "new", TTL))
				.isEqualTo(RefreshSessionRotationResult.notFound());
		assertThat(store.find("sid-1")).isEmpty();
	}

	@Test
	void 같은_RT를_동시에_교체하면_하나만_성공하고_토큰_계열은_폐기된다() throws Exception {
		store.save("sid-1", new RefreshSession(1L, "old"), TTL);
		ExecutorService executor = Executors.newFixedThreadPool(2);
		CountDownLatch ready = new CountDownLatch(2);
		CountDownLatch start = new CountDownLatch(1);
		try {
			Future<RefreshSessionRotationResult> first = executor.submit(
					() -> rotateAfterSignal(ready, start, "new-1"));
			Future<RefreshSessionRotationResult> second = executor.submit(
					() -> rotateAfterSignal(ready, start, "new-2"));
			assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
			start.countDown();

			assertThat(List.of(first.get(5, TimeUnit.SECONDS), second.get(5, TimeUnit.SECONDS)))
					.extracting(RefreshSessionRotationResult::status)
					.containsExactlyInAnyOrder(
							RefreshSessionRotationResult.Status.ROTATED,
							RefreshSessionRotationResult.Status.REUSED);
			assertThat(store.find("sid-1")).isEmpty();
		} finally {
			executor.shutdownNow();
		}
	}

	private RefreshSessionRotationResult rotateAfterSignal(
			CountDownLatch ready,
			CountDownLatch start,
			String newHash
	) throws InterruptedException {
		ready.countDown();
		start.await();
		return store.rotate("sid-1", "old", newHash, TTL);
	}

	@Test
	void deleteAllByUserId는_해당_사용자_세션만_지우고_삭제한_수를_반환한다() {
		store.save("a-1", new RefreshSession(1L, "h1"), TTL);
		store.save("a-2", new RefreshSession(1L, "h2"), TTL);
		store.save("b-1", new RefreshSession(2L, "h3"), TTL);

		int deleted = store.deleteAllByUserId(1L);

		assertThat(deleted).isEqualTo(2);
		assertThat(store.find("a-1")).isEmpty();
		assertThat(store.find("a-2")).isEmpty();
		assertThat(store.find("b-1")).contains(new RefreshSession(2L, "h3"));
	}

	@Test
	void deleteAllByUserId는_세션이_없으면_0을_반환한다() {
		assertThat(store.deleteAllByUserId(99L)).isZero();
	}
}

package com.starlightnews.backend.global.security;

import java.time.Duration;
import java.util.Optional;

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

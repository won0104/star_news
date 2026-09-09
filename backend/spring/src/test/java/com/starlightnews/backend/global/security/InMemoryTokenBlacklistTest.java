package com.starlightnews.backend.global.security;

import java.time.Duration;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class InMemoryTokenBlacklistTest {

	private static final Duration TTL = Duration.ofMinutes(30);

	private InMemoryTokenBlacklist blacklist;

	@BeforeEach
	void setUp() {
		blacklist = new InMemoryTokenBlacklist();
	}

	@Test
	void 등록한_jti는_블랙리스트로_조회된다() {
		blacklist.blacklist("jti-1", TTL);

		assertThat(blacklist.isBlacklisted("jti-1")).isTrue();
	}

	@Test
	void 등록하지_않은_jti는_블랙리스트가_아니다() {
		assertThat(blacklist.isBlacklisted("unknown")).isFalse();
	}

	@Test
	void TTL이_지난_jti는_블랙리스트에서_해제된다() {
		blacklist.blacklist("jti-1", Duration.ofSeconds(-1));

		assertThat(blacklist.isBlacklisted("jti-1")).isFalse();
	}
}

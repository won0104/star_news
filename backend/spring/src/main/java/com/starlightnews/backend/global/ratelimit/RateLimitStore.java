package com.starlightnews.backend.global.ratelimit;

import java.time.Duration;

/**
 * 요청·실패 횟수를 키별로 세는 저장소. 로그인 시도 제한과 요약 생성 제한이 함께 쓴다.
 *
 * <p>app.auth.store 로 구현을 고른다. memory 는 인스턴스마다 따로 세므로 단일 인스턴스(로컬·개발)용이고,
 * 운영은 redis 로 두어 재시작·다중 인스턴스에서도 같은 횟수를 본다. 인증 저장소와 같은 스위치를 쓰는
 * 이유는 두 기능 모두 "Redis 가 있으면 Redis 에 둔다"는 같은 판단이기 때문이다.
 */
public interface RateLimitStore {

	/**
	 * 고정 창 방식으로 1 올리고 올린 뒤 값을 돌려준다.
	 * 창은 키가 처음 만들어질 때 시작해 window 가 지나면 0 부터 다시 센다.
	 */
	long incrementInWindow(String key, Duration window);

	/**
	 * 1 올리고 만료를 ttl 뒤로 다시 미룬다. 올린 뒤 값을 돌려준다.
	 * 마지막으로 올린 뒤 ttl 동안 아무 일이 없어야 0 으로 돌아간다(연속 실패 잠금에 쓴다).
	 */
	long incrementAndExtend(String key, Duration ttl);

	/** 현재 횟수. 없거나 만료됐으면 0. */
	long count(String key);

	/** 횟수를 지운다. */
	void reset(String key);
}

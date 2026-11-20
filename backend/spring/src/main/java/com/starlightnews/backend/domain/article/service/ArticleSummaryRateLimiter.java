package com.starlightnews.backend.domain.article.service;

import com.starlightnews.backend.domain.article.config.ArticleSummaryRateLimitProperties;
import com.starlightnews.backend.domain.article.exception.ArticleErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.ratelimit.RateLimitStore;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * 기사 요약 생성(유료 GMS 호출) 횟수를 제한한다.
 *
 * <p>로그인 사용자는 사용자 ID 로, 비로그인 요청은 클라이언트 IP 로 센다. 사용자 ID 를 우선하는 이유는
 * 같은 강의실(한 공인 IP)의 로그인 사용자들이 서로의 한도를 깎아 먹지 않게 하기 위해서다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ArticleSummaryRateLimiter {

	private static final String USER_KEY_PREFIX = "summary:user:";
	private static final String IP_KEY_PREFIX = "summary:ip:";
	/** IP 를 알 수 없는 비로그인 요청. 필터가 늘 채우므로 실제로는 오지 않는다. */
	private static final String UNKNOWN_IP = "unknown";

	private final RateLimitStore store;
	private final ArticleSummaryRateLimitProperties properties;

	/**
	 * GMS 를 부르기 직전에 한 번 센다. 한도를 넘으면 부르지 않고 막는다.
	 *
	 * @param userId   로그인 사용자 ID. 비로그인이면 null
	 * @param clientIp 클라이언트 IP. 비로그인일 때 키로 쓴다
	 * @throws BusinessException SUMMARY_RATE_LIMITED
	 */
	public void acquire(Long userId, String clientIp) {
		boolean authenticated = userId != null;
		String key = authenticated
				? USER_KEY_PREFIX + userId
				: IP_KEY_PREFIX + (clientIp == null ? UNKNOWN_IP : clientIp);
		int limit = authenticated ? properties.userLimit() : properties.guestLimit();

		long count = store.incrementInWindow(key, properties.window());
		if (count > limit) {
			if (count == limit + 1L) {
				log.warn("기사 요약 생성 한도를 넘었습니다. key={}, limit={}, window={}",
						key, limit, properties.window());
			}
			throw new BusinessException(ArticleErrorCode.SUMMARY_RATE_LIMITED);
		}
	}
}

package com.starlightnews.backend.domain.auth.service;

import java.util.Locale;

import com.starlightnews.backend.domain.auth.config.LoginAttemptProperties;
import com.starlightnews.backend.domain.auth.exception.AuthErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.ratelimit.RateLimitStore;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * 로그인 무차별 대입을 막는다.
 *
 * <p>두 가지를 센다.
 * <ul>
 *   <li>계정별 연속 실패: maxFailures 번 틀리면 마지막 실패로부터 lockDuration 동안 잠근다. 성공하면 지운다.</li>
 *   <li>IP 별 실패: ipWindow 동안 ipMaxFailures 번을 넘으면 그 IP 의 로그인을 막는다. 계정을 바꿔 가며
 *       한두 번씩 찌르는(password spraying) 경우를 계정 잠금만으로는 막을 수 없다.</li>
 * </ul>
 *
 * <p>계정 존재 여부를 드러내지 않도록, 없는 아이디도 똑같이 세고 똑같이 잠근다. 잠긴 동안은 비밀번호를
 * 확인하지 않으므로 맞는 비밀번호를 넣어도 같은 429 가 나간다.
 *
 * <p>계정 키는 호출하는 쪽이 정한다({@link #subjectOf}). 있는 계정은 사용자 ID 로 센다. MySQL 의 기본
 * 콜레이션(utf8mb4_0900_ai_ci)은 대소문자·악센트를 구분하지 않아 "Admin"·"ádmin" 도 같은 계정을 찾는데,
 * 입력 문자열로 세면 철자만 바꿔 한도를 비켜 갈 수 있기 때문이다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class LoginAttemptLimiter {

	private static final String SUBJECT_KEY_PREFIX = "login:fail:subject:";
	private static final String IP_KEY_PREFIX = "login:fail:ip:";

	private final RateLimitStore store;
	private final LoginAttemptProperties properties;

	/** 있는 계정이면 사용자 ID, 없으면 정규화한 입력 아이디로 계정 키를 만든다. */
	public static String subjectOf(Long userId, String loginId) {
		if (userId != null) {
			return "user:" + userId;
		}
		return "id:" + loginId.strip().toLowerCase(Locale.ROOT);
	}

	/**
	 * 잠겨 있으면 막는다. 비밀번호를 확인하기 전에 불러야 한다.
	 *
	 * @throws BusinessException LOGIN_ATTEMPTS_EXCEEDED
	 */
	public void checkAllowed(String subject, String clientIp) {
		if (store.count(SUBJECT_KEY_PREFIX + subject) >= properties.maxFailures()) {
			throw new BusinessException(AuthErrorCode.LOGIN_ATTEMPTS_EXCEEDED);
		}
		if (clientIp != null && store.count(IP_KEY_PREFIX + clientIp) >= properties.ipMaxFailures()) {
			throw new BusinessException(AuthErrorCode.LOGIN_ATTEMPTS_EXCEEDED);
		}
	}

	/** 실패를 기록한다. 이번 실패로 잠기면 남긴다(공격 흔적을 찾을 수 있게). */
	public void recordFailure(String subject, String clientIp) {
		long failures = store.incrementAndExtend(SUBJECT_KEY_PREFIX + subject, properties.lockDuration());
		if (failures == properties.maxFailures()) {
			log.warn("로그인 연속 실패로 계정을 잠급니다. subject={}, clientIp={}, lock={}",
					subject, clientIp, properties.lockDuration());
		}
		if (clientIp == null) {
			return;
		}
		long ipFailures = store.incrementInWindow(IP_KEY_PREFIX + clientIp, properties.ipWindow());
		if (ipFailures == properties.ipMaxFailures()) {
			log.warn("한 IP 의 로그인 실패가 한도에 닿았습니다. clientIp={}, window={}",
					clientIp, properties.ipWindow());
		}
	}

	/** 성공하면 계정의 연속 실패를 지운다. IP 실패 수는 다른 계정 시도까지 포함하므로 지우지 않는다. */
	public void recordSuccess(String subject) {
		store.reset(SUBJECT_KEY_PREFIX + subject);
	}
}

package com.starlightnews.backend.domain.auth.config;

import java.time.Duration;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * 로그인 시도 제한(무차별 대입 방지) 설정.
 *
 * @param maxFailures   한 계정에 연속으로 몇 번 틀리면 잠글지. 성공하면 0 으로 돌아간다
 * @param lockDuration  잠금 시간. 마지막 실패로부터 이 시간이 지나야 다시 시도할 수 있다.
 *                      실패할 때마다 다시 세므로, 잠기기 전 실패 사이가 이보다 길면 횟수가 초기화된다
 * @param ipMaxFailures 한 IP 에서 ipWindow 동안 허용하는 실패 수. 계정을 바꿔 가며 찌르는 것을 막는다.
 *                      강의실·발표장처럼 여러 사람이 한 공인 IP 를 쓰므로 계정 한도보다 넉넉히 둔다
 * @param ipWindow      IP 실패 수를 세는 고정 창
 */
@Validated
@ConfigurationProperties(prefix = "app.auth.login-attempt")
public record LoginAttemptProperties(
		@Min(1) @Max(100) int maxFailures,
		@NotNull Duration lockDuration,
		@Min(1) @Max(10_000) int ipMaxFailures,
		@NotNull Duration ipWindow
) {

	@AssertTrue(message = "app.auth.login-attempt.lock-duration 과 ip-window 는 0 보다 커야 합니다.")
	public boolean isDurationsPositive() {
		return isPositive(lockDuration) && isPositive(ipWindow);
	}

	private static boolean isPositive(Duration duration) {
		return duration == null || (!duration.isZero() && !duration.isNegative());
	}
}

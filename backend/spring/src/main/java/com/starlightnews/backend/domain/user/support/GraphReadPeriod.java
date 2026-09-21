package com.starlightnews.backend.domain.user.support;

import java.time.LocalDate;
import java.time.LocalDateTime;

import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;

/** KST 날짜 기준의 마지막 열람 기간. 양쪽 날짜를 모두 포함한다. */
public record GraphReadPeriod(LocalDate from, LocalDate to) {

	public GraphReadPeriod {
		if (from == null || to == null || from.isAfter(to) || to.equals(LocalDate.MAX)) {
			throw new BusinessException(CommonErrorCode.INVALID_INPUT_VALUE);
		}
	}

	public static GraphReadPeriod optional(LocalDate from, LocalDate to) {
		return from == null && to == null ? null : new GraphReadPeriod(from, to);
	}

	public LocalDateTime fromInclusive() {
		return from.atStartOfDay();
	}

	public LocalDateTime toExclusive() {
		return to.plusDays(1).atStartOfDay();
	}
}

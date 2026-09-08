package com.starlightnews.backend.domain.auth.dto;

/**
 * 로그인 아이디 사용 가능 여부 조회 응답. 중복은 오류가 아니라 available 값으로 반환한다.
 */
public record LoginIdAvailabilityResponse(
		String loginId,
		boolean available
) {
}

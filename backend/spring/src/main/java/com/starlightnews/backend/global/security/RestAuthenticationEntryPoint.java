package com.starlightnews.backend.global.security;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.global.error.CommonErrorCode;
import com.starlightnews.backend.global.error.ErrorCode;
import com.starlightnews.backend.global.error.ErrorResponse;
import com.starlightnews.backend.global.request.RequestIdFilter;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;

/**
 * 인증 실패(401) 를 공통 ErrorResponse 형식으로 응답한다.
 * 필터 계층에서 발생하므로 GlobalExceptionHandler 가 아니라 여기서 직접 JSON 을 쓴다.
 */
public class RestAuthenticationEntryPoint implements AuthenticationEntryPoint {

	private final ObjectMapper objectMapper;

	public RestAuthenticationEntryPoint(ObjectMapper objectMapper) {
		this.objectMapper = objectMapper;
	}

	@Override
	public void commence(
			HttpServletRequest request,
			HttpServletResponse response,
			AuthenticationException authException
	) throws IOException {
		ErrorCode errorCode = resolveErrorCode(request);

		ErrorResponse body = ErrorResponse.of(
				errorCode,
				request.getRequestURI(),
				RequestIdFilter.getRequestId(request));

		response.setStatus(errorCode.getStatus().value());
		response.setContentType(MediaType.APPLICATION_JSON_VALUE);
		response.setCharacterEncoding(StandardCharsets.UTF_8.name());
		objectMapper.writeValue(response.getWriter(), body);
	}

	private ErrorCode resolveErrorCode(HttpServletRequest request) {
		Object attribute = request.getAttribute(JwtAuthenticationFilter.JWT_ERROR_ATTRIBUTE);
		if (attribute instanceof JwtValidationException exception) {
			return exception.getReason() == JwtValidationException.Reason.EXPIRED
					? CommonErrorCode.EXPIRED_ACCESS_TOKEN
					: CommonErrorCode.INVALID_ACCESS_TOKEN;
		}
		return CommonErrorCode.UNAUTHORIZED;
	}
}

package com.starlightnews.backend.global.request;

import java.io.IOException;
import java.util.UUID;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class RequestIdFilter extends OncePerRequestFilter {

	public static final String HEADER_NAME = "X-Request-Id";
	public static final String ATTRIBUTE_NAME = "starlightNews.requestId";
	private static final String MDC_KEY = "requestId";

	@Override
	protected void doFilterInternal(
			HttpServletRequest request,
			HttpServletResponse response,
			FilterChain filterChain
	) throws ServletException, IOException {
		String requestId = resolveRequestId(request);
		request.setAttribute(ATTRIBUTE_NAME, requestId);
		response.setHeader(HEADER_NAME, requestId);
		MDC.put(MDC_KEY, requestId);

		try {
			filterChain.doFilter(request, response);
		} finally {
			MDC.remove(MDC_KEY);
		}
	}

	public static String getRequestId(HttpServletRequest request) {
		Object requestId = request.getAttribute(ATTRIBUTE_NAME);
		if (requestId instanceof String value) {
			return value;
		}

		String generatedRequestId = UUID.randomUUID().toString();
		request.setAttribute(ATTRIBUTE_NAME, generatedRequestId);
		return generatedRequestId;
	}

	private String resolveRequestId(HttpServletRequest request) {
		String requestId = request.getHeader(HEADER_NAME);
		if (requestId == null) {
			return UUID.randomUUID().toString();
		}

		try {
			return UUID.fromString(requestId).toString();
		} catch (IllegalArgumentException exception) {
			return UUID.randomUUID().toString();
		}
	}
}

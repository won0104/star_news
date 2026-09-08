package com.starlightnews.backend.global.request;

import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class RequestIdFilterTest {

	private final RequestIdFilter requestIdFilter = new RequestIdFilter();

	@Test
	void generatesRequestIdAndSharesItWithHeaderAttributeAndMdc() throws Exception {
		MockHttpServletRequest request = new MockHttpServletRequest();
		MockHttpServletResponse response = new MockHttpServletResponse();

		requestIdFilter.doFilterInternal(request, response, (servletRequest, servletResponse) -> {
			String requestId = (String) request.getAttribute(RequestIdFilter.ATTRIBUTE_NAME);

			assertDoesNotThrow(() -> UUID.fromString(requestId));
			assertEquals(requestId, response.getHeader(RequestIdFilter.HEADER_NAME));
			assertEquals(requestId, MDC.get("requestId"));
		});

		assertNull(MDC.get("requestId"));
	}

	@Test
	void keepsValidIncomingRequestId() throws Exception {
		String requestId = UUID.randomUUID().toString();
		MockHttpServletRequest request = new MockHttpServletRequest();
		MockHttpServletResponse response = new MockHttpServletResponse();
		request.addHeader(RequestIdFilter.HEADER_NAME, requestId);

		requestIdFilter.doFilterInternal(request, response, (servletRequest, servletResponse) -> {
		});

		assertEquals(requestId, response.getHeader(RequestIdFilter.HEADER_NAME));
	}

	@Test
	void replacesInvalidIncomingRequestId() throws Exception {
		MockHttpServletRequest request = new MockHttpServletRequest();
		MockHttpServletResponse response = new MockHttpServletResponse();
		request.addHeader(RequestIdFilter.HEADER_NAME, "invalid-request-id");

		requestIdFilter.doFilterInternal(request, response, (servletRequest, servletResponse) -> {
		});

		String generatedRequestId = response.getHeader(RequestIdFilter.HEADER_NAME);
		assertNotEquals("invalid-request-id", generatedRequestId);
		assertDoesNotThrow(() -> UUID.fromString(generatedRequestId));
	}
}

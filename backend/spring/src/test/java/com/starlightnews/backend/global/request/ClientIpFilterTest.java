package com.starlightnews.backend.global.request;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.assertj.core.api.Assertions.assertThat;

class ClientIpFilterTest {

	private static String filter(ClientIpFilter filter, MockHttpServletRequest request) throws Exception {
		filter.doFilter(request, new MockHttpServletResponse(), (req, res) -> {
		});
		return (String) request.getAttribute(ClientIpFilter.ATTRIBUTE_NAME);
	}

	private static MockHttpServletRequest request(String remoteAddr) {
		MockHttpServletRequest request = new MockHttpServletRequest();
		request.setRemoteAddr(remoteAddr);
		return request;
	}

	@Test
	void 헤더를_설정하지_않으면_remoteAddr를_쓰고_클라이언트가_보낸_헤더는_무시한다() throws Exception {
		MockHttpServletRequest request = request("10.0.0.1");
		request.addHeader("X-Real-IP", "1.2.3.4");
		request.addHeader("X-Forwarded-For", "5.6.7.8");

		assertThat(filter(new ClientIpFilter(""), request)).isEqualTo("10.0.0.1");
	}

	@Test
	void 프록시가_덮어쓰는_헤더를_설정하면_그_값을_쓴다() throws Exception {
		MockHttpServletRequest request = request("172.17.0.1");
		request.addHeader("X-Real-IP", " 203.0.113.10 ");

		assertThat(filter(new ClientIpFilter("X-Real-IP"), request)).isEqualTo("203.0.113.10");
	}

	@Test
	void 설정한_헤더가_없거나_비면_remoteAddr로_돌아간다() throws Exception {
		MockHttpServletRequest missing = request("172.17.0.1");
		MockHttpServletRequest blank = request("172.17.0.1");
		blank.addHeader("X-Real-IP", "  ");

		assertThat(filter(new ClientIpFilter("X-Real-IP"), missing)).isEqualTo("172.17.0.1");
		assertThat(filter(new ClientIpFilter("X-Real-IP"), blank)).isEqualTo("172.17.0.1");
	}

	@Test
	void IP로_볼_수_없게_긴_값은_믿지_않는다() throws Exception {
		MockHttpServletRequest request = request("172.17.0.1");
		request.addHeader("X-Real-IP", "a".repeat(65));

		assertThat(filter(new ClientIpFilter("X-Real-IP"), request)).isEqualTo("172.17.0.1");
	}
}

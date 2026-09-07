package com.starlightnews.backend.global.config;

import com.starlightnews.backend.global.constant.ApiPaths;
import com.starlightnews.backend.global.request.RequestIdFilter;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest
@Import({CorsConfig.class, CorsConfigTest.TestController.class})
@ActiveProfiles("test")
class CorsConfigTest {

	private static final String ALLOWED_ORIGIN = "http://localhost:3000";
	private static final String DENIED_ORIGIN = "https://not-allowed.example";
	private static final String TEST_PATH = ApiPaths.API_V1 + "/cors-test";

	@Autowired
	private MockMvc mockMvc;

	@Test
	void allowsPreflightRequestFromConfiguredOrigin() throws Exception {
		mockMvc.perform(options(TEST_PATH)
					.header(HttpHeaders.ORIGIN, ALLOWED_ORIGIN)
					.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET"))
				.andExpect(status().isOk())
				.andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, ALLOWED_ORIGIN))
				.andExpect(header().string(
						HttpHeaders.ACCESS_CONTROL_ALLOW_METHODS,
						containsString("GET")
				));
	}

	@Test
	void rejectsPreflightRequestFromUnconfiguredOrigin() throws Exception {
		mockMvc.perform(options(TEST_PATH)
					.header(HttpHeaders.ORIGIN, DENIED_ORIGIN)
					.header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET"))
				.andExpect(status().isForbidden())
				.andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
	}

	@Test
	void exposesRequestIdHeaderToConfiguredOrigin() throws Exception {
		mockMvc.perform(get(TEST_PATH)
					.header(HttpHeaders.ORIGIN, ALLOWED_ORIGIN))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, ALLOWED_ORIGIN))
				.andExpect(header().string(
						HttpHeaders.ACCESS_CONTROL_EXPOSE_HEADERS,
						containsString(RequestIdFilter.HEADER_NAME)
				));
	}

	@RestController
	@RequestMapping(ApiPaths.API_V1 + "/cors-test")
	static class TestController {

		@GetMapping
		String get() {
			return "ok";
		}
	}
}

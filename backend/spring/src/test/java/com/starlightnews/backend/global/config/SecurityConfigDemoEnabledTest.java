package com.starlightnews.backend.global.config;

import com.starlightnews.backend.global.security.InMemoryTokenBlacklist;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** 시연 기능을 켰을 때(app.demo.enabled=true)만 시연 경로가 로그인 없이 열리는지 확인한다. */
@WebMvcTest(
		controllers = SecurityConfigDemoEnabledTest.DemoController.class,
		properties = "app.demo.enabled=true")
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class,
		SecurityConfigDemoEnabledTest.DemoController.class})
@ActiveProfiles("test")
class SecurityConfigDemoEnabledTest {

	@Autowired
	private MockMvc mockMvc;

	@Test
	void 시연_기능을_켜면_시연_경로는_토큰_없이_접근할_수_있다() throws Exception {
		mockMvc.perform(post("/api/v1/demo/articles"))
				.andExpect(status().isCreated());
		mockMvc.perform(get("/api/v1/demo/articles/1/graph"))
				.andExpect(status().isOk());
	}

	@Test
	void 시연_기능을_켜도_다른_보호_경로는_그대로_인증이_필요하다() throws Exception {
		mockMvc.perform(get("/api/v1/secure/ping"))
				.andExpect(status().isUnauthorized());
	}

	@RestController
	static class DemoController {

		@PostMapping("/api/v1/demo/articles")
		ResponseEntity<String> create() {
			return ResponseEntity.status(HttpStatus.CREATED).body("created");
		}

		@GetMapping("/api/v1/demo/articles/1/graph")
		String graph() {
			return "graph";
		}

		@GetMapping("/api/v1/secure/ping")
		String ping() {
			return "pong";
		}
	}
}

package com.starlightnews.backend.global.config;

import com.starlightnews.backend.global.security.InMemoryTokenBlacklist;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = SecurityConfigTest.ProtectedController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class, SecurityConfigTest.ProtectedController.class})
@ActiveProfiles("test")
class SecurityConfigTest {

	private static final String PROTECTED_PATH = "/api/v1/secure/ping";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@Test
	void 홈_GET_요청은_토큰_없이_접근할_수_있다() throws Exception {
		mockMvc.perform(get("/api/v1/home"))
				.andExpect(status().isOk());
	}

	@Test
	void 홈_POST_요청은_공개하지_않는다() throws Exception {
		mockMvc.perform(post("/api/v1/home"))
				.andExpect(status().isUnauthorized());
	}

	@Test
	void 홈_하위_경로는_공개하지_않는다() throws Exception {
		mockMvc.perform(get("/api/v1/home/private"))
				.andExpect(status().isUnauthorized());
	}

	@Test
	void 공개_경로가_아닌_요청에_토큰이_없으면_401_UNAUTHORIZED_JSON을_응답한다() throws Exception {
		mockMvc.perform(get(PROTECTED_PATH))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.status").value(401))
				.andExpect(jsonPath("$.code").value("UNAUTHORIZED"))
				.andExpect(jsonPath("$.path").value(PROTECTED_PATH))
				.andExpect(jsonPath("$.requestId").isString())
				.andExpect(jsonPath("$.errors").isArray());
	}

	@Test
	void 잘못된_토큰이면_401_INVALID_ACCESS_TOKEN을_응답한다() throws Exception {
		mockMvc.perform(get(PROTECTED_PATH).header(HttpHeaders.AUTHORIZATION, "Bearer garbage"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("INVALID_ACCESS_TOKEN"));
	}

	@Test
	void 유효한_토큰이면_보호_경로에_접근할_수_있다() throws Exception {
		String token = jwtProvider.createAccessToken(1L);

		mockMvc.perform(get(PROTECTED_PATH).header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
				.andExpect(status().isOk());
	}

	@RestController
	static class ProtectedController {

		@GetMapping("/api/v1/home")
		String home() {
			return "home";
		}

		@GetMapping(PROTECTED_PATH)
		String ping() {
			return "pong";
		}
	}
}

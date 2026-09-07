package com.starlightnews.backend.global.error;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class GlobalExceptionHandlerTest {

	private MockMvc mockMvc;

	@BeforeEach
	void setUp() {
		mockMvc = MockMvcBuilders
				.standaloneSetup(new TestController())
				.setControllerAdvice(new GlobalExceptionHandler())
				.build();
	}

	@Test
	void businessExceptionReturnsDefinedErrorResponse() throws Exception {
		mockMvc.perform(get("/test/business-error"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.status").value(400))
				.andExpect(jsonPath("$.code").value("COMMON_001"))
				.andExpect(jsonPath("$.message").value("입력값이 올바르지 않습니다."))
				.andExpect(jsonPath("$.path").value("/test/business-error"))
				.andExpect(jsonPath("$.errors").isArray());
	}

	@Test
	void invalidRequestBodyReturnsFieldErrors() throws Exception {
		mockMvc.perform(post("/test/validation")
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"name\":\"\"}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_001"))
				.andExpect(jsonPath("$.errors[0].field").value("name"))
				.andExpect(jsonPath("$.errors[0].message").value("이름은 필수입니다."));
	}

	@Test
	void malformedJsonReturnsMalformedRequestError() throws Exception {
		mockMvc.perform(post("/test/validation")
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"name\":"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_002"));
	}

	@Test
	void wrongPathVariableTypeReturnsTypeMismatchError() throws Exception {
		mockMvc.perform(get("/test/numbers/not-a-number"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("COMMON_003"))
				.andExpect(jsonPath("$.errors[0].field").value("number"));
	}

	@Test
	void unexpectedExceptionDoesNotExposeInternalDetails() throws Exception {
		mockMvc.perform(get("/test/unexpected-error"))
				.andExpect(status().isInternalServerError())
				.andExpect(jsonPath("$.code").value("COMMON_500"))
				.andExpect(jsonPath("$.message").value("서버 내부 오류가 발생했습니다."));
	}

	@RestController
	@RequestMapping("/test")
	static class TestController {

		@GetMapping("/business-error")
		void businessError() {
			throw new BusinessException(ErrorCode.INVALID_INPUT_VALUE);
		}

		@PostMapping("/validation")
		void validate(@Valid @RequestBody TestRequest request) {
		}

		@GetMapping("/numbers/{number}")
		void number(@PathVariable Long number) {
		}

		@GetMapping("/unexpected-error")
		void unexpectedError() {
			throw new IllegalStateException("sensitive internal detail");
		}
	}

	record TestRequest(
			@NotBlank(message = "이름은 필수입니다.") String name
	) {
	}
}

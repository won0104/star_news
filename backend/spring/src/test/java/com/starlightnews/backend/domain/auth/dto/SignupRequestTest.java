package com.starlightnews.backend.domain.auth.dto;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class SignupRequestTest {

	private static ValidatorFactory validatorFactory;
	private static Validator validator;

	@BeforeAll
	static void setUp() {
		validatorFactory = Validation.buildDefaultValidatorFactory();
		validator = validatorFactory.getValidator();
	}

	@AfterAll
	static void tearDown() {
		validatorFactory.close();
	}

	private SignupRequest request(String loginId, String password, String nickname) {
		return new SignupRequest(loginId, password, nickname, null, null);
	}

	private Set<String> invalidFields(SignupRequest request) {
		return validator.validate(request).stream()
				.map(ConstraintViolation::getPropertyPath)
				.map(Object::toString)
				.collect(Collectors.toSet());
	}

	@Test
	void 정상_요청은_제약_위반이_없다() {
		assertThat(validator.validate(request("starlight01", "password1234", "별빛"))).isEmpty();
	}

	@Test
	void loginId가_null이거나_비어_있으면_위반이다() {
		assertThat(invalidFields(request(null, "password1234", "별빛"))).contains("loginId");
		assertThat(invalidFields(request("   ", "password1234", "별빛"))).contains("loginId");
	}

	@Test
	void loginId가_4자_미만이면_위반이다() {
		assertThat(invalidFields(request("abc", "password1234", "별빛"))).contains("loginId");
	}

	@Test
	void loginId가_50자를_초과하면_위반이다() {
		assertThat(invalidFields(request("a".repeat(51), "password1234", "별빛"))).contains("loginId");
	}

	@Test
	void loginId에_허용되지_않는_문자가_있으면_위반이다() {
		assertThat(invalidFields(request("Starlight01", "password1234", "별빛"))).contains("loginId"); // 대문자
		assertThat(invalidFields(request("star-light", "password1234", "별빛"))).contains("loginId");  // 하이픈
		assertThat(invalidFields(request("스타라이트", "password1234", "별빛"))).contains("loginId");   // 한글
	}

	@Test
	void loginId는_영문소문자_숫자_밑줄_조합_4에서50자면_통과한다() {
		assertThat(validator.validate(request("a_b_1234", "password1234", "별빛"))).isEmpty();
		assertThat(validator.validate(request("abcd", "password1234", "별빛"))).isEmpty();
	}

	@Test
	void password가_8자_미만이면_위반이다() {
		assertThat(invalidFields(request("starlight01", "pass123", "별빛"))).contains("password");
	}

	@Test
	void password가_20자를_초과하면_위반이다() {
		assertThat(invalidFields(request("starlight01", "p".repeat(21), "별빛"))).contains("password");
	}

	@Test
	void nickname이_2자_미만이면_위반이다() {
		assertThat(invalidFields(request("starlight01", "password1234", "별"))).contains("nickname");
	}

	@Test
	void nickname이_50자를_초과하면_위반이다() {
		assertThat(invalidFields(request("starlight01", "password1234", "별".repeat(51)))).contains("nickname");
	}

	@Test
	void 여러_필드가_동시에_틀리면_모두_위반으로_보고된다() {
		Set<String> fields = invalidFields(request("ab", "short", ""));

		assertThat(fields).contains("loginId", "password", "nickname");
	}

	@Test
	void 관심_비관심_배열은_생략하면_빈_리스트로_정규화된다() {
		SignupRequest request = new SignupRequest("starlight01", "password1234", "별빛", null, null);

		assertThat(validator.validate(request)).isEmpty();
		assertThat(request.interestedTopicCodes()).isEmpty();
		assertThat(request.dislikedTopicCodes()).isEmpty();
	}

	@Test
	void 관심_비관심_배열은_전달한_값을_보존한다() {
		SignupRequest request = new SignupRequest(
				"starlight01", "password1234", "별빛",
				List.of("ECONOMY", "IT_SCIENCE"), List.of("SPORTS"));

		assertThat(request.interestedTopicCodes()).containsExactly("ECONOMY", "IT_SCIENCE");
		assertThat(request.dislikedTopicCodes()).containsExactly("SPORTS");
	}
}

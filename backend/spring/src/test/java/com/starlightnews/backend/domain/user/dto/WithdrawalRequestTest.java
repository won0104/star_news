package com.starlightnews.backend.domain.user.dto;

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

class WithdrawalRequestTest {

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

	private Set<String> invalidFields(WithdrawalRequest request) {
		return validator.validate(request).stream()
				.map(ConstraintViolation::getPropertyPath)
				.map(Object::toString)
				.collect(Collectors.toSet());
	}

	@Test
	void 비밀번호가_있으면_제약_위반이_없다() {
		assertThat(validator.validate(new WithdrawalRequest("password1234"))).isEmpty();
	}

	@Test
	void 비밀번호가_null이면_위반이다() {
		assertThat(invalidFields(new WithdrawalRequest(null))).contains("password");
	}

	@Test
	void 비밀번호가_공백뿐이면_위반이다() {
		assertThat(invalidFields(new WithdrawalRequest("   "))).contains("password");
	}
}

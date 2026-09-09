package com.starlightnews.backend.domain.user.service;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

import com.starlightnews.backend.domain.auth.exception.AuthErrorCode;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.security.RefreshSessionStore;
import com.starlightnews.backend.global.security.TokenBlacklist;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {

	@Mock
	private UserRepository userRepository;

	@Mock
	private PasswordEncoder passwordEncoder;

	@Mock
	private RefreshSessionStore refreshSessionStore;

	@Mock
	private TokenBlacklist tokenBlacklist;

	@InjectMocks
	private UserService userService;

	private User activeUser(long id) {
		User user = User.create("starlight01", "hashed-password", "별빛");
		ReflectionTestUtils.setField(user, "id", id);
		return user;
	}

	private AuthErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return (AuthErrorCode) ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 탈퇴하면_계정을_soft_delete하고_세션전체를_삭제하고_jti를_블랙리스트한다() {
		User user = activeUser(1L);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));
		given(passwordEncoder.matches("password1234", "hashed-password")).willReturn(true);
		Instant expiresAt = Instant.now().plus(Duration.ofMinutes(30));

		userService.withdraw(1L, "jti-1", expiresAt, "password1234");

		assertThat(user.isDeleted()).isTrue();
		verify(refreshSessionStore).deleteAllByUserId(1L);

		ArgumentCaptor<Duration> ttl = ArgumentCaptor.forClass(Duration.class);
		verify(tokenBlacklist).blacklist(eq("jti-1"), ttl.capture());
		assertThat(ttl.getValue()).isBetween(Duration.ofMinutes(29), Duration.ofMinutes(30));
	}

	@Test
	void 비밀번호가_틀리면_INVALID_CREDENTIALS_예외이고_계정은_유지된다() {
		User user = activeUser(1L);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));
		given(passwordEncoder.matches("wrong-password", "hashed-password")).willReturn(false);

		Throwable thrown = catchThrowable(
				() -> userService.withdraw(1L, "jti-1", Instant.now().plus(Duration.ofMinutes(30)), "wrong-password"));

		assertThat(errorCodeOf(thrown)).isEqualTo(AuthErrorCode.INVALID_CREDENTIALS);
		assertThat(user.isDeleted()).isFalse();
		verify(refreshSessionStore, never()).deleteAllByUserId(anyLong());
		verify(tokenBlacklist, never()).blacklist(any(), any());
	}

	@Test
	void 이미_탈퇴한_회원이면_USER_DELETED_예외이고_비밀번호는_확인하지_않는다() {
		User deleted = activeUser(1L);
		deleted.markDeleted();
		given(userRepository.findById(1L)).willReturn(Optional.of(deleted));

		Throwable thrown = catchThrowable(
				() -> userService.withdraw(1L, "jti-1", Instant.now().plus(Duration.ofMinutes(30)), "password1234"));

		assertThat(errorCodeOf(thrown)).isEqualTo(AuthErrorCode.USER_DELETED);
		verify(passwordEncoder, never()).matches(any(), any());
		verify(refreshSessionStore, never()).deleteAllByUserId(anyLong());
	}

	@Test
	void 사용자가_존재하지_않으면_USER_DELETED_예외() {
		given(userRepository.findById(1L)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(
				() -> userService.withdraw(1L, "jti-1", Instant.now().plus(Duration.ofMinutes(30)), "password1234"));

		assertThat(errorCodeOf(thrown)).isEqualTo(AuthErrorCode.USER_DELETED);
	}

	@Test
	void 이미_만료된_AT로_탈퇴하면_블랙리스트_TTL은_0이다() {
		User user = activeUser(1L);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));
		given(passwordEncoder.matches("password1234", "hashed-password")).willReturn(true);

		userService.withdraw(1L, "jti-1", Instant.now().minus(Duration.ofMinutes(1)), "password1234");

		verify(tokenBlacklist).blacklist("jti-1", Duration.ZERO);
	}
}

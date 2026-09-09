package com.starlightnews.backend.domain.auth.service;

import java.time.Duration;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.auth.dto.LoginIdAvailabilityResponse;
import com.starlightnews.backend.domain.auth.dto.LoginRequest;
import com.starlightnews.backend.domain.auth.dto.LoginResult;
import com.starlightnews.backend.domain.auth.dto.SignupRequest;
import com.starlightnews.backend.domain.auth.dto.SignupResponse;
import com.starlightnews.backend.domain.auth.exception.AuthErrorCode;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.domain.UserInterest;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.security.JwtProvider;
import com.starlightnews.backend.global.security.RefreshSession;
import com.starlightnews.backend.global.security.RefreshSessionStore;
import com.starlightnews.backend.global.security.TokenHasher;
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
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

	@Mock
	private UserRepository userRepository;

	@Mock
	private PasswordEncoder passwordEncoder;

	@Mock
	private JwtProvider jwtProvider;

	@Mock
	private RefreshSessionStore refreshSessionStore;

	@InjectMocks
	private AuthService authService;

	private SignupRequest request(List<String> interested, List<String> disliked) {
		return new SignupRequest("starlight01", "password1234", "별빛", interested, disliked);
	}

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
	void 관심분야_없이_회원가입하면_사용자를_저장하고_응답을_반환한다() {
		given(userRepository.existsByLoginId("starlight01")).willReturn(false);
		given(passwordEncoder.encode("password1234")).willReturn("hashed-password");
		given(userRepository.save(any(User.class))).willAnswer(invocation -> invocation.getArgument(0));

		SignupResponse response = authService.signup(request(null, null));

		assertThat(response.loginId()).isEqualTo("starlight01");
		assertThat(response.nickname()).isEqualTo("별빛");
		assertThat(response.interestedTopicCodes()).isEmpty();
		assertThat(response.dislikedTopicCodes()).isEmpty();

		ArgumentCaptor<User> savedUser = ArgumentCaptor.forClass(User.class);
		verify(userRepository).save(savedUser.capture());
		assertThat(savedUser.getValue().getPasswordHash()).isEqualTo("hashed-password");
		assertThat(savedUser.getValue().getInterests()).isEmpty();
	}

	@Test
	void 관심_비관심_분야를_포함해_회원가입하면_모두_저장한다() {
		given(userRepository.existsByLoginId("starlight01")).willReturn(false);
		given(passwordEncoder.encode("password1234")).willReturn("hashed-password");
		given(userRepository.save(any(User.class))).willAnswer(invocation -> invocation.getArgument(0));

		SignupResponse response = authService.signup(
				request(List.of("ECONOMY", "IT_SCIENCE"), List.of("SPORTS")));

		assertThat(response.interestedTopicCodes())
				.containsExactly(TopicCode.ECONOMY, TopicCode.IT_SCIENCE);
		assertThat(response.dislikedTopicCodes()).containsExactly(TopicCode.SPORTS);

		ArgumentCaptor<User> savedUser = ArgumentCaptor.forClass(User.class);
		verify(userRepository).save(savedUser.capture());
		assertThat(savedUser.getValue().getInterests())
				.extracting(interest -> interest.getId().getTopicCode(), UserInterest::getInterestType)
				.containsExactlyInAnyOrder(
						tuple(TopicCode.ECONOMY, InterestType.INTEREST),
						tuple(TopicCode.IT_SCIENCE, InterestType.INTEREST),
						tuple(TopicCode.SPORTS, InterestType.DISLIKE)
				);
	}

	@Test
	void 로그인_아이디가_이미_존재하면_LOGIN_ID_ALREADY_EXISTS_예외() {
		given(userRepository.existsByLoginId("starlight01")).willReturn(true);

		Throwable thrown = catchThrowable(() -> authService.signup(request(null, null)));

		assertThat(errorCodeOf(thrown)).isEqualTo(AuthErrorCode.LOGIN_ID_ALREADY_EXISTS);
		verify(userRepository, never()).save(any());
	}

	@Test
	void 같은_배열에_같은_토픽이_중복이면_DUPLICATED_TOPIC_예외() {
		Throwable thrown = catchThrowable(
				() -> authService.signup(request(List.of("ECONOMY", "ECONOMY"), null)));

		assertThat(errorCodeOf(thrown)).isEqualTo(AuthErrorCode.DUPLICATED_TOPIC);
		verify(userRepository, never()).save(any());
	}

	@Test
	void 관심과_비관심에_같은_토픽이_있으면_TOPIC_SELECTION_CONFLICT_예외() {
		Throwable thrown = catchThrowable(
				() -> authService.signup(request(List.of("ECONOMY"), List.of("ECONOMY"))));

		assertThat(errorCodeOf(thrown)).isEqualTo(AuthErrorCode.TOPIC_SELECTION_CONFLICT);
		verify(userRepository, never()).save(any());
	}

	@Test
	void 존재하지_않는_토픽_코드면_INVALID_TOPIC_예외() {
		Throwable thrown = catchThrowable(
				() -> authService.signup(request(List.of("MOVIE"), null)));

		assertThat(errorCodeOf(thrown)).isEqualTo(AuthErrorCode.INVALID_TOPIC);
		verify(userRepository, never()).save(any());
	}

	@Test
	void 토픽_검증은_로그인_아이디_중복_확인보다_먼저_수행된다() {
		catchThrowable(() -> authService.signup(request(List.of("MOVIE"), null)));

		verify(userRepository, never()).existsByLoginId(any());
	}

	@Test
	void 사용_중이_아닌_로그인_아이디는_available_true를_반환한다() {
		given(userRepository.existsByLoginId("newbie123")).willReturn(false);

		LoginIdAvailabilityResponse response = authService.checkLoginIdAvailability("newbie123");

		assertThat(response.loginId()).isEqualTo("newbie123");
		assertThat(response.available()).isTrue();
	}

	@Test
	void 이미_사용_중인_로그인_아이디는_available_false를_반환한다() {
		given(userRepository.existsByLoginId("starlight01")).willReturn(true);

		LoginIdAvailabilityResponse response = authService.checkLoginIdAvailability("starlight01");

		assertThat(response.loginId()).isEqualTo("starlight01");
		assertThat(response.available()).isFalse();
	}

	private LoginRequest loginRequest() {
		return new LoginRequest("starlight01", "password1234");
	}

	private void stubTokenIssuance() {
		given(jwtProvider.createAccessToken(1L)).willReturn("access-token-value");
		given(jwtProvider.createRefreshToken(anyString())).willReturn("refresh-token-value");
		given(jwtProvider.accessTokenValidity()).willReturn(Duration.ofSeconds(3600));
		given(jwtProvider.refreshTokenValidity()).willReturn(Duration.ofDays(14));
	}

	@Test
	void 로그인_성공시_토큰을_발급하고_Refresh_세션을_저장한다() {
		given(userRepository.findByLoginId("starlight01")).willReturn(Optional.of(activeUser(1L)));
		given(passwordEncoder.matches("password1234", "hashed-password")).willReturn(true);
		stubTokenIssuance();

		LoginResult result = authService.login(loginRequest());

		assertThat(result.response().accessToken()).isEqualTo("access-token-value");
		assertThat(result.response().tokenType()).isEqualTo("Bearer");
		assertThat(result.response().expiresIn()).isEqualTo(3600);
		assertThat(result.response().user())
				.isEqualTo(new com.starlightnews.backend.domain.auth.dto.LoginResponse.UserSummary(1L, "starlight01", "별빛"));
		assertThat(result.refreshToken()).isEqualTo("refresh-token-value");
		assertThat(result.refreshTokenMaxAgeSeconds()).isEqualTo(Duration.ofDays(14).toSeconds());

		ArgumentCaptor<String> sessionId = ArgumentCaptor.forClass(String.class);
		ArgumentCaptor<RefreshSession> session = ArgumentCaptor.forClass(RefreshSession.class);
		ArgumentCaptor<Duration> ttl = ArgumentCaptor.forClass(Duration.class);
		verify(refreshSessionStore).save(sessionId.capture(), session.capture(), ttl.capture());

		assertThat(sessionId.getValue()).isNotBlank();
		assertThat(session.getValue().userId()).isEqualTo(1L);
		assertThat(session.getValue().refreshTokenHash())
				.isEqualTo(TokenHasher.sha256Hex("refresh-token-value"))
				.isNotEqualTo("refresh-token-value");
		assertThat(ttl.getValue()).isEqualTo(Duration.ofDays(14));
	}

	@Test
	void 존재하지_않는_로그인_아이디면_INVALID_CREDENTIALS_예외() {
		given(userRepository.findByLoginId("starlight01")).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> authService.login(loginRequest()));

		assertThat(errorCodeOf(thrown)).isEqualTo(AuthErrorCode.INVALID_CREDENTIALS);
		verify(refreshSessionStore, never()).save(any(), any(), any());
	}

	@Test
	void 비밀번호가_틀리면_INVALID_CREDENTIALS_예외() {
		given(userRepository.findByLoginId("starlight01")).willReturn(Optional.of(activeUser(1L)));
		given(passwordEncoder.matches("password1234", "hashed-password")).willReturn(false);

		Throwable thrown = catchThrowable(() -> authService.login(loginRequest()));

		assertThat(errorCodeOf(thrown)).isEqualTo(AuthErrorCode.INVALID_CREDENTIALS);
		verify(refreshSessionStore, never()).save(any(), any(), any());
	}

	@Test
	void 탈퇴한_회원이면_비밀번호_확인_전에_USER_DELETED_예외() {
		User deleted = activeUser(1L);
		deleted.markDeleted();
		given(userRepository.findByLoginId("starlight01")).willReturn(Optional.of(deleted));

		Throwable thrown = catchThrowable(() -> authService.login(loginRequest()));

		assertThat(errorCodeOf(thrown)).isEqualTo(AuthErrorCode.USER_DELETED);
		verify(passwordEncoder, never()).matches(any(), any());
		verify(refreshSessionStore, never()).save(any(), any(), any());
	}
}

package com.starlightnews.backend.domain.auth.service;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import com.starlightnews.backend.domain.auth.dto.LoginIdAvailabilityResponse;
import com.starlightnews.backend.domain.auth.dto.LoginRequest;
import com.starlightnews.backend.domain.auth.dto.LoginResponse;
import com.starlightnews.backend.domain.auth.dto.LoginResult;
import com.starlightnews.backend.domain.auth.dto.RefreshResponse;
import com.starlightnews.backend.domain.auth.dto.RefreshResult;
import com.starlightnews.backend.domain.auth.dto.SignupRequest;
import com.starlightnews.backend.domain.auth.dto.SignupResponse;
import com.starlightnews.backend.domain.auth.exception.AuthErrorCode;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.security.JwtProvider;
import com.starlightnews.backend.global.security.JwtValidationException;
import com.starlightnews.backend.global.security.RefreshSession;
import com.starlightnews.backend.global.security.RefreshSessionStore;
import com.starlightnews.backend.global.security.TokenBlacklist;
import com.starlightnews.backend.global.security.TokenHasher;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class AuthService {

	private static final String TOKEN_TYPE_BEARER = "Bearer";

	private final UserRepository userRepository;
	private final PasswordEncoder passwordEncoder;
	private final JwtProvider jwtProvider;
	private final RefreshSessionStore refreshSessionStore;
	private final TokenBlacklist tokenBlacklist;

	@Transactional(readOnly = true)
	public LoginIdAvailabilityResponse checkLoginIdAvailability(String loginId) {
		boolean available = !userRepository.existsByLoginId(loginId);
		return new LoginIdAvailabilityResponse(loginId, available);
	}

	@Transactional(readOnly = true)
	public LoginResult login(LoginRequest request) {
		User user = userRepository.findByLoginId(request.loginId())
				.orElseThrow(() -> new BusinessException(AuthErrorCode.INVALID_CREDENTIALS));

		if (user.isDeleted()) {
			throw new BusinessException(AuthErrorCode.USER_DELETED);
		}
		if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
			throw new BusinessException(AuthErrorCode.INVALID_CREDENTIALS);
		}

		String sessionId = UUID.randomUUID().toString();
		String accessToken = jwtProvider.createAccessToken(user.getId());
		String refreshToken = jwtProvider.createRefreshToken(sessionId);

		refreshSessionStore.save(
				sessionId,
				new RefreshSession(user.getId(), TokenHasher.sha256Hex(refreshToken)),
				jwtProvider.refreshTokenValidity());

		LoginResponse response = new LoginResponse(
				accessToken,
				TOKEN_TYPE_BEARER,
				jwtProvider.accessTokenValidity().toSeconds(),
				new LoginResponse.UserSummary(user.getId(), user.getLoginId(), user.getNickname()));

		return new LoginResult(response, refreshToken, jwtProvider.refreshTokenValidity().toSeconds());
	}

	@Transactional(readOnly = true)
	public RefreshResult refresh(String refreshToken) {
		if (refreshToken == null || refreshToken.isBlank()) {
			throw new BusinessException(AuthErrorCode.INVALID_REFRESH_TOKEN);
		}

		String sessionId = parseRefreshSessionId(refreshToken);

		RefreshSession session = refreshSessionStore.find(sessionId)
				.orElseThrow(() -> new BusinessException(AuthErrorCode.REFRESH_SESSION_NOT_FOUND));

		if (!session.refreshTokenHash().equals(TokenHasher.sha256Hex(refreshToken))) {
			throw new BusinessException(AuthErrorCode.REFRESH_SESSION_NOT_FOUND);
		}

		User user = userRepository.findById(session.userId())
				.orElseThrow(() -> new BusinessException(AuthErrorCode.REFRESH_SESSION_NOT_FOUND));
		if (user.isDeleted()) {
			throw new BusinessException(AuthErrorCode.USER_DELETED);
		}

		refreshSessionStore.delete(sessionId);

		String newSessionId = UUID.randomUUID().toString();
		String newAccessToken = jwtProvider.createAccessToken(user.getId());
		String newRefreshToken = jwtProvider.createRefreshToken(newSessionId);
		refreshSessionStore.save(
				newSessionId,
				new RefreshSession(user.getId(), TokenHasher.sha256Hex(newRefreshToken)),
				jwtProvider.refreshTokenValidity());

		RefreshResponse response = new RefreshResponse(
				newAccessToken,
				TOKEN_TYPE_BEARER,
				jwtProvider.accessTokenValidity().toSeconds());

		return new RefreshResult(response, newRefreshToken, jwtProvider.refreshTokenValidity().toSeconds());
	}

	// 토큰 만료, 서명깨짐, 형식 이상, 타입 확인
	private String parseRefreshSessionId(String refreshToken) {
		try {
			return jwtProvider.parseRefreshTokenSessionId(refreshToken);
		} catch (JwtValidationException exception) {
			AuthErrorCode errorCode = exception.getReason() == JwtValidationException.Reason.EXPIRED
					? AuthErrorCode.EXPIRED_REFRESH_TOKEN
					: AuthErrorCode.INVALID_REFRESH_TOKEN;
			throw new BusinessException(errorCode);
		}
	}

	/**
	 * 로그아웃. Refresh 세션을 지우고, 현재 Access Token 의 jti 를 남은 만료 시간 동안 블랙리스트에 등록한다.
	 * RT 가 없거나 이미 무효여도 로그아웃은 성공 처리한다.
	 */
	@Transactional(readOnly = true)
	public void logout(String accessTokenJti, Instant accessTokenExpiresAt, String refreshToken) {
		deleteRefreshSessionQuietly(refreshToken);

		Duration remaining = Duration.between(Instant.now(), accessTokenExpiresAt);
		if (remaining.isNegative()) {
			remaining = Duration.ZERO;
		}
		tokenBlacklist.blacklist(accessTokenJti, remaining);
	}

	private void deleteRefreshSessionQuietly(String refreshToken) {
		if (refreshToken == null || refreshToken.isBlank()) {
			return;
		}
		try {
			refreshSessionStore.delete(jwtProvider.parseRefreshTokenSessionId(refreshToken));
		} catch (JwtValidationException ignored) {
			// RT 가 만료·무효여도 로그아웃은 계속 진행한다.
		}
	}

	@Transactional
	public SignupResponse signup(SignupRequest request) {
		List<TopicCode> interestedTopics = parseDistinctTopics(request.interestedTopicCodes());
		List<TopicCode> dislikedTopics = parseDistinctTopics(request.dislikedTopicCodes());
		validateNoSelectionConflict(interestedTopics, dislikedTopics);

		if (userRepository.existsByLoginId(request.loginId())) {
			throw new BusinessException(AuthErrorCode.LOGIN_ID_ALREADY_EXISTS);
		}

		User user = User.create(
				request.loginId(),
				passwordEncoder.encode(request.password()),
				request.nickname());
		interestedTopics.forEach(topic -> user.addInterest(topic, InterestType.INTEREST));
		dislikedTopics.forEach(topic -> user.addInterest(topic, InterestType.DISLIKE));

		User savedUser = userRepository.save(user);

		return new SignupResponse(
				savedUser.getId(),
				savedUser.getLoginId(),
				savedUser.getNickname(),
				interestedTopics,
				dislikedTopics);
	}

	private List<TopicCode> parseDistinctTopics(List<String> rawTopicCodes) {
		List<TopicCode> topics = new ArrayList<>();
		for (String rawTopicCode : rawTopicCodes) {
			TopicCode topic = TopicCode.from(rawTopicCode)
					.orElseThrow(() -> new BusinessException(AuthErrorCode.INVALID_TOPIC));
			if (topics.contains(topic)) {
				throw new BusinessException(AuthErrorCode.DUPLICATED_TOPIC);
			}
			topics.add(topic);
		}
		return topics;
	}

	private void validateNoSelectionConflict(List<TopicCode> interestedTopics, List<TopicCode> dislikedTopics) {
		boolean hasConflict = interestedTopics.stream().anyMatch(dislikedTopics::contains);
		if (hasConflict) {
			throw new BusinessException(AuthErrorCode.TOPIC_SELECTION_CONFLICT);
		}
	}
}

package com.starlightnews.backend.domain.user.service;

import java.time.Duration;
import java.time.Instant;

import com.starlightnews.backend.domain.auth.exception.AuthErrorCode;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.security.RefreshSessionStore;
import com.starlightnews.backend.global.security.TokenBlacklist;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class UserService {

	private final UserRepository userRepository;
	private final PasswordEncoder passwordEncoder;
	private final RefreshSessionStore refreshSessionStore;
	private final TokenBlacklist tokenBlacklist;

	/**
	 * 회원 탈퇴. 계정을 soft delete(deleted_at)로 비활성화하고, 해당 사용자의 모든 Refresh 세션을 삭제하며,
	 * 현재 Access Token 의 jti 를 남은 만료 시간 동안 블랙리스트에 등록한다.
	 * 민감한 작업이므로 현재 비밀번호를 다시 확인한다.
	 * 개인화 데이터(user_interest 등)는 여기서 지우지 않는다. (추후 하드 퍼지 배치에서 정리)
	 */
	@Transactional
	public void withdraw(long userId, String accessTokenJti, Instant accessTokenExpiresAt, String rawPassword) {
		User user = userRepository.findById(userId)
				.filter(found -> !found.isDeleted())
				.orElseThrow(() -> new BusinessException(AuthErrorCode.USER_DELETED));

		if (!passwordEncoder.matches(rawPassword, user.getPasswordHash())) {
			throw new BusinessException(AuthErrorCode.INVALID_CREDENTIALS);
		}

		user.markDeleted();
		refreshSessionStore.deleteAllByUserId(userId);

		Duration remaining = Duration.between(Instant.now(), accessTokenExpiresAt);
		if (remaining.isNegative()) {
			remaining = Duration.ZERO;
		}
		tokenBlacklist.blacklist(accessTokenJti, remaining);
	}
}

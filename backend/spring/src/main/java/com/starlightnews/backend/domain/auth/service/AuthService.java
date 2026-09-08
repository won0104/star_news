package com.starlightnews.backend.domain.auth.service;

import java.util.ArrayList;
import java.util.List;

import com.starlightnews.backend.domain.auth.dto.LoginIdAvailabilityResponse;
import com.starlightnews.backend.domain.auth.dto.SignupRequest;
import com.starlightnews.backend.domain.auth.dto.SignupResponse;
import com.starlightnews.backend.domain.auth.exception.AuthErrorCode;
import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class AuthService {

	private final UserRepository userRepository;
	private final PasswordEncoder passwordEncoder;

	@Transactional(readOnly = true)
	public LoginIdAvailabilityResponse checkLoginIdAvailability(String loginId) {
		boolean available = !userRepository.existsByLoginId(loginId);
		return new LoginIdAvailabilityResponse(loginId, available);
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

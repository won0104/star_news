package com.starlightnews.backend.domain.user.service;

import java.util.LinkedHashSet;
import java.util.Set;

import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.dto.TopicPreferenceResponse;
import com.starlightnews.backend.domain.user.dto.UpdateTopicPreferenceRequest;
import com.starlightnews.backend.domain.user.exception.UserErrorCode;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 로그인 사용자의 관심·비관심 Topic 설정을 조회하고 관리한다.
 */
@Service
@RequiredArgsConstructor
public class TopicPreferenceService {

	private final UserRepository userRepository;

	/**
	 * 활성 사용자가 설정한 관심 Topic 목록을 반환한다.
	 * 사용자가 없거나 탈퇴한 경우 USER_NOT_FOUND 예외를 발생시킨다.
	 */
	@Transactional(readOnly = true)
	public TopicPreferenceResponse getInterests(long userId) {
		User user = findActiveUser(userId);
		return new TopicPreferenceResponse(user.getTopicCodes(InterestType.INTEREST));
	}

	/**
	 * 활성 사용자가 설정한 비관심 Topic 목록을 반환한다.
	 * 사용자가 없거나 탈퇴한 경우 USER_NOT_FOUND 예외를 발생시킨다.
	 */
	@Transactional(readOnly = true)
	public TopicPreferenceResponse getDislikes(long userId) {
		User user = findActiveUser(userId);
		return new TopicPreferenceResponse(user.getTopicCodes(InterestType.DISLIKE));
	}

	/**
	 * 요청 목록을 활성 사용자의 최종 관심 Topic 상태로 저장한다.
	 */
	@Transactional
	public TopicPreferenceResponse replaceInterests(long userId, UpdateTopicPreferenceRequest request) {
		Set<TopicCode> requestedTopics = parseDistinctTopics(request.topicCodes());
		User user = findActiveUser(userId);

		user.replaceTopicPreferences(InterestType.INTEREST, requestedTopics);
		return new TopicPreferenceResponse(user.getTopicCodes(InterestType.INTEREST));
	}

	/**
	 * 요청 목록을 활성 사용자의 최종 비관심 Topic 상태로 저장한다.
	 */
	@Transactional
	public TopicPreferenceResponse replaceDislikes(long userId, UpdateTopicPreferenceRequest request) {
		Set<TopicCode> requestedTopics = parseDistinctTopics(request.topicCodes());
		User user = findActiveUser(userId);

		user.replaceTopicPreferences(InterestType.DISLIKE, requestedTopics);
		return new TopicPreferenceResponse(user.getTopicCodes(InterestType.DISLIKE));
	}

	private User findActiveUser(long userId) {
		return userRepository.findById(userId)
				.filter(found -> !found.isDeleted())
				.orElseThrow(() -> new BusinessException(UserErrorCode.USER_NOT_FOUND));
	}

	private Set<TopicCode> parseDistinctTopics(Iterable<String> rawTopicCodes) {
		Set<TopicCode> topics = new LinkedHashSet<>();
		for (String rawTopicCode : rawTopicCodes) {
			TopicCode topic = TopicCode.from(rawTopicCode)
					.orElseThrow(() -> new BusinessException(UserErrorCode.INVALID_TOPIC));
			if (!topics.add(topic)) {
				throw new BusinessException(UserErrorCode.DUPLICATED_TOPIC);
			}
		}
		return topics;
	}
}

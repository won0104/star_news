package com.starlightnews.backend.domain.user.service;

import java.util.Optional;

import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.dto.TopicPreferenceResponse;
import com.starlightnews.backend.domain.user.exception.UserErrorCode;
import com.starlightnews.backend.domain.user.repository.UserRepository;
import com.starlightnews.backend.global.enums.InterestType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class TopicPreferenceServiceTest {

	@Mock
	private UserRepository userRepository;

	@InjectMocks
	private TopicPreferenceService topicPreferenceService;

	private User activeUser() {
		return User.create("starlight01", "hashed-password", "별빛");
	}

	private UserErrorCode errorCodeOf(Throwable throwable) {
		assertThat(throwable).isInstanceOf(BusinessException.class);
		return (UserErrorCode) ((BusinessException) throwable).getErrorCode();
	}

	@Test
	void 관심_Topic만_Enum_선언_순서로_반환한다() {
		User user = activeUser();
		user.addInterest(TopicCode.IT_SCIENCE, InterestType.INTEREST);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		user.addInterest(TopicCode.POLITICS, InterestType.INTEREST);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));

		TopicPreferenceResponse response = topicPreferenceService.getInterests(1L);

		assertThat(response.topicCodes())
				.containsExactly(TopicCode.POLITICS, TopicCode.IT_SCIENCE);
	}

	@Test
	void 설정한_관심_Topic이_없으면_빈_목록을_반환한다() {
		User user = activeUser();
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));

		TopicPreferenceResponse response = topicPreferenceService.getInterests(1L);

		assertThat(response.topicCodes()).isEmpty();
	}

	@Test
	void 사용자가_존재하지_않으면_USER_NOT_FOUND_예외() {
		given(userRepository.findById(1L)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> topicPreferenceService.getInterests(1L));

		assertThat(errorCodeOf(thrown)).isEqualTo(UserErrorCode.USER_NOT_FOUND);
	}

	@Test
	void 탈퇴한_사용자이면_USER_NOT_FOUND_예외() {
		User user = activeUser();
		user.markDeleted();
		given(userRepository.findById(1L)).willReturn(Optional.of(user));

		Throwable thrown = catchThrowable(() -> topicPreferenceService.getInterests(1L));

		assertThat(errorCodeOf(thrown)).isEqualTo(UserErrorCode.USER_NOT_FOUND);
	}
}

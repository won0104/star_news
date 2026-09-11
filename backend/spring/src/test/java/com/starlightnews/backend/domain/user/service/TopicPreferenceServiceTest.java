package com.starlightnews.backend.domain.user.service;

import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.user.domain.User;
import com.starlightnews.backend.domain.user.dto.TopicPreferenceResponse;
import com.starlightnews.backend.domain.user.dto.UpdateTopicPreferenceRequest;
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
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

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

	@Test
	void 비관심_Topic만_Enum_선언_순서로_반환한다() {
		User user = activeUser();
		user.addInterest(TopicCode.IT_SCIENCE, InterestType.DISLIKE);
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		user.addInterest(TopicCode.POLITICS, InterestType.DISLIKE);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));

		TopicPreferenceResponse response = topicPreferenceService.getDislikes(1L);

		assertThat(response.topicCodes())
				.containsExactly(TopicCode.POLITICS, TopicCode.IT_SCIENCE);
	}

	@Test
	void 설정한_비관심_Topic이_없으면_빈_목록을_반환한다() {
		User user = activeUser();
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));

		TopicPreferenceResponse response = topicPreferenceService.getDislikes(1L);

		assertThat(response.topicCodes()).isEmpty();
	}

	@Test
	void 비관심_Topic_조회시_사용자가_존재하지_않으면_USER_NOT_FOUND_예외() {
		given(userRepository.findById(1L)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> topicPreferenceService.getDislikes(1L));

		assertThat(errorCodeOf(thrown)).isEqualTo(UserErrorCode.USER_NOT_FOUND);
	}

	@Test
	void 비관심_Topic_조회시_탈퇴한_사용자이면_USER_NOT_FOUND_예외() {
		User user = activeUser();
		user.markDeleted();
		given(userRepository.findById(1L)).willReturn(Optional.of(user));

		Throwable thrown = catchThrowable(() -> topicPreferenceService.getDislikes(1L));

		assertThat(errorCodeOf(thrown)).isEqualTo(UserErrorCode.USER_NOT_FOUND);
	}

	@Test
	void 요청_목록을_최종_관심_Topic으로_반영한다() {
		User user = activeUser();
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		user.addInterest(TopicCode.IT_SCIENCE, InterestType.INTEREST);
		user.addInterest(TopicCode.POLITICS, InterestType.DISLIKE);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));
		UpdateTopicPreferenceRequest request = new UpdateTopicPreferenceRequest(
				List.of(" politics ", "CULTURE", "IT_SCIENCE"));

		TopicPreferenceResponse response = topicPreferenceService.replaceInterests(1L, request);

		assertThat(response.topicCodes())
				.containsExactly(TopicCode.POLITICS, TopicCode.CULTURE, TopicCode.IT_SCIENCE);
		assertThat(user.getTopicCodes(InterestType.DISLIKE))
				.containsExactly(TopicCode.SPORTS);
	}

	@Test
	void 빈_배열이면_관심_Topic만_모두_해제한다() {
		User user = activeUser();
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));

		TopicPreferenceResponse response = topicPreferenceService.replaceInterests(
				1L, new UpdateTopicPreferenceRequest(List.of()));

		assertThat(response.topicCodes()).isEmpty();
		assertThat(user.getTopicCodes(InterestType.DISLIKE))
				.containsExactly(TopicCode.SPORTS);
	}

	@Test
	void 존재하지_않는_Topic이면_INVALID_TOPIC_예외() {
		UpdateTopicPreferenceRequest request = new UpdateTopicPreferenceRequest(List.of("MOVIE"));

		Throwable thrown = catchThrowable(() -> topicPreferenceService.replaceInterests(1L, request));

		assertThat(errorCodeOf(thrown)).isEqualTo(UserErrorCode.INVALID_TOPIC);
		verify(userRepository, never()).findById(anyLong());
	}

	@Test
	void 정규화한_Topic이_중복이면_DUPLICATED_TOPIC_예외() {
		UpdateTopicPreferenceRequest request = new UpdateTopicPreferenceRequest(
				List.of("POLITICS", " politics "));

		Throwable thrown = catchThrowable(() -> topicPreferenceService.replaceInterests(1L, request));

		assertThat(errorCodeOf(thrown)).isEqualTo(UserErrorCode.DUPLICATED_TOPIC);
		verify(userRepository, never()).findById(anyLong());
	}

	@Test
	void 관심_Topic_변경시_사용자가_없으면_USER_NOT_FOUND_예외() {
		given(userRepository.findById(1L)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> topicPreferenceService.replaceInterests(
				1L, new UpdateTopicPreferenceRequest(List.of("POLITICS"))));

		assertThat(errorCodeOf(thrown)).isEqualTo(UserErrorCode.USER_NOT_FOUND);
	}

	@Test
	void 요청_목록을_최종_비관심_Topic으로_반영한다() {
		User user = activeUser();
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		user.addInterest(TopicCode.IT_SCIENCE, InterestType.INTEREST);
		user.addInterest(TopicCode.POLITICS, InterestType.DISLIKE);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));
		UpdateTopicPreferenceRequest request = new UpdateTopicPreferenceRequest(
				List.of(" economy ", "CULTURE", "SPORTS"));

		TopicPreferenceResponse response = topicPreferenceService.replaceDislikes(1L, request);

		assertThat(response.topicCodes())
				.containsExactly(TopicCode.ECONOMY, TopicCode.CULTURE, TopicCode.SPORTS);
		assertThat(user.getTopicCodes(InterestType.INTEREST))
				.containsExactly(TopicCode.IT_SCIENCE);
	}

	@Test
	void 빈_배열이면_비관심_Topic만_모두_해제한다() {
		User user = activeUser();
		user.addInterest(TopicCode.ECONOMY, InterestType.INTEREST);
		user.addInterest(TopicCode.SPORTS, InterestType.DISLIKE);
		given(userRepository.findById(1L)).willReturn(Optional.of(user));

		TopicPreferenceResponse response = topicPreferenceService.replaceDislikes(
				1L, new UpdateTopicPreferenceRequest(List.of()));

		assertThat(response.topicCodes()).isEmpty();
		assertThat(user.getTopicCodes(InterestType.INTEREST))
				.containsExactly(TopicCode.ECONOMY);
	}

	@Test
	void 비관심_변경시_존재하지_않는_Topic이면_INVALID_TOPIC_예외() {
		UpdateTopicPreferenceRequest request = new UpdateTopicPreferenceRequest(List.of("MOVIE"));

		Throwable thrown = catchThrowable(() -> topicPreferenceService.replaceDislikes(1L, request));

		assertThat(errorCodeOf(thrown)).isEqualTo(UserErrorCode.INVALID_TOPIC);
		verify(userRepository, never()).findById(anyLong());
	}

	@Test
	void 비관심_변경시_정규화한_Topic이_중복이면_DUPLICATED_TOPIC_예외() {
		UpdateTopicPreferenceRequest request = new UpdateTopicPreferenceRequest(
				List.of("POLITICS", " politics "));

		Throwable thrown = catchThrowable(() -> topicPreferenceService.replaceDislikes(1L, request));

		assertThat(errorCodeOf(thrown)).isEqualTo(UserErrorCode.DUPLICATED_TOPIC);
		verify(userRepository, never()).findById(anyLong());
	}

	@Test
	void 비관심_Topic_변경시_사용자가_없으면_USER_NOT_FOUND_예외() {
		given(userRepository.findById(1L)).willReturn(Optional.empty());

		Throwable thrown = catchThrowable(() -> topicPreferenceService.replaceDislikes(
				1L, new UpdateTopicPreferenceRequest(List.of("POLITICS"))));

		assertThat(errorCodeOf(thrown)).isEqualTo(UserErrorCode.USER_NOT_FOUND);
	}
}

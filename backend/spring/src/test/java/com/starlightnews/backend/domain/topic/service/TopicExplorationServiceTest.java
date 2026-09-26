package com.starlightnews.backend.domain.topic.service;

import java.time.Clock;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.topic.domain.TopicExplorationEntry;
import com.starlightnews.backend.domain.topic.dto.TopicExplorationResponse;
import com.starlightnews.backend.domain.topic.exception.TopicExplorationErrorCode;
import com.starlightnews.backend.domain.topic.repository.TopicExplorationEntryRepository;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class TopicExplorationServiceTest {

	private static final LocalDateTime SNAPSHOT_AT = LocalDateTime.of(2026, 9, 24, 18, 0);
	private static final LocalDateTime NOW = LocalDateTime.of(2026, 9, 24, 19, 0);

	@Mock
	private TopicExplorationEntryRepository topicExplorationEntryRepository;

	private TopicExplorationService topicExplorationService;

	@BeforeEach
	void setUp() {
		Clock clock = Clock.fixed(NOW.atOffset(ZoneOffset.ofHours(9)).toInstant(), ZoneOffset.UTC);
		topicExplorationService = new TopicExplorationService(topicExplorationEntryRepository, clock);
	}

	@Test
	void 중심_Topic과_저장된_Event를_응답으로_변환한다() {
		TopicExplorationEntry entry = entry(201L, 1, "economy-event-1", "한국은행 기준금리 동결", 23);
		given(topicExplorationEntryRepository.findLatestEntries(
				TopicCode.ECONOMY, NOW, PageRequest.of(0, 10))).willReturn(List.of(entry));

		TopicExplorationResponse response = topicExplorationService.getTopicExploration("economy");

		assertThat(response.snapshotAt()).isEqualTo(OffsetDateTime.parse("2026-09-24T18:00:00+09:00"));
		assertThat(response.centerTopic()).isEqualTo(new TopicExplorationResponse.CenterTopic(
				NodeType.TOPIC, TopicCode.ECONOMY, "경제"));
		assertThat(response.entryNodes()).containsExactly(new TopicExplorationResponse.EntryNode(
				201L, 1, NodeType.EVENT, "economy-event-1", "한국은행 기준금리 동결", 23));
		verify(topicExplorationEntryRepository).findLatestEntries(
				TopicCode.ECONOMY, NOW, PageRequest.of(0, 10));
	}

	@Test
	void 저장된_결과가_없어도_중심_Topic과_빈_목록을_반환한다() {
		given(topicExplorationEntryRepository.findLatestEntries(
				TopicCode.SPORTS, NOW, PageRequest.of(0, 10))).willReturn(List.of());

		TopicExplorationResponse response = topicExplorationService.getTopicExploration("SPORTS");

		assertThat(response.snapshotAt()).isNull();
		assertThat(response.centerTopic().topicCode()).isEqualTo(TopicCode.SPORTS);
		assertThat(response.centerTopic().label()).isEqualTo("스포츠");
		assertThat(response.entryNodes()).isEmpty();
	}

	@Test
	void 지원하지_않는_Topic은_INVALID_TOPIC_CODE를_반환한다() {
		assertThatThrownBy(() -> topicExplorationService.getTopicExploration("UNKNOWN"))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TopicExplorationErrorCode.INVALID_TOPIC_CODE));
		verifyNoInteractions(topicExplorationEntryRepository);
	}

	@Test
	void 조회_실패는_TOPIC_EXPLORATION_FETCH_FAILED로_변환한다() {
		given(topicExplorationEntryRepository.findLatestEntries(
				TopicCode.ECONOMY, NOW, PageRequest.of(0, 10)))
				.willThrow(new DataAccessResourceFailureException("DB 연결 실패"));

		assertThatThrownBy(() -> topicExplorationService.getTopicExploration("ECONOMY"))
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(TopicExplorationErrorCode.TOPIC_EXPLORATION_FETCH_FAILED));
	}

	private TopicExplorationEntry entry(
			Long id,
			int rank,
			String nodeId,
			String title,
			int articleCount
	) {
		TopicExplorationEntry entry = new TopicExplorationEntry(
				SNAPSHOT_AT, TopicCode.ECONOMY, nodeId, title, rank, articleCount);
		ReflectionTestUtils.setField(entry, "topicExplorationEntryId", id);
		return entry;
	}
}

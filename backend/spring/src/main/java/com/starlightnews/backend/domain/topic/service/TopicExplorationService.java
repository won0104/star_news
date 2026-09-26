package com.starlightnews.backend.domain.topic.service;

import java.time.Clock;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.topic.domain.TopicExplorationEntry;
import com.starlightnews.backend.domain.topic.dto.TopicExplorationResponse;
import com.starlightnews.backend.domain.topic.exception.TopicExplorationErrorCode;
import com.starlightnews.backend.domain.topic.repository.TopicExplorationEntryRepository;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 선택한 Topic의 공개 시각이 지난 최신 탐색 진입 Event를 MySQL에서 조회한다.
 * 요청 시 Neo4j를 조회하거나 탐색 순위를 다시 계산하지 않는다.
 */
@Slf4j
@Service
public class TopicExplorationService {

	private static final int ENTRY_LIMIT = 10;
	private static final ZoneId KST_ZONE = ZoneId.of("Asia/Seoul");
	private static final ZoneOffset KST_OFFSET = ZoneOffset.ofHours(9);

	private final TopicExplorationEntryRepository topicExplorationEntryRepository;
	private final Clock topicExplorationClock;

	public TopicExplorationService(
			TopicExplorationEntryRepository topicExplorationEntryRepository,
			@Qualifier("topicExplorationClock") Clock topicExplorationClock
	) {
		this.topicExplorationEntryRepository = topicExplorationEntryRepository;
		this.topicExplorationClock = topicExplorationClock;
	}

	@Transactional(readOnly = true)
	public TopicExplorationResponse getTopicExploration(String rawTopicCode) {
		TopicCode topicCode = TopicCode.from(rawTopicCode)
				.orElseThrow(() -> new BusinessException(TopicExplorationErrorCode.INVALID_TOPIC_CODE));
		TopicExplorationResponse.CenterTopic centerTopic = new TopicExplorationResponse.CenterTopic(
				NodeType.TOPIC,
				topicCode,
				topicCode.labelKo());

		try {
			LocalDateTime now = LocalDateTime.ofInstant(topicExplorationClock.instant(), KST_ZONE);
			List<TopicExplorationEntry> entries = topicExplorationEntryRepository.findLatestEntries(
					topicCode,
					now,
					PageRequest.of(0, ENTRY_LIMIT));
			if (entries.isEmpty()) {
				return new TopicExplorationResponse(null, centerTopic, List.of());
			}

			List<TopicExplorationResponse.EntryNode> entryNodes = entries.stream()
					.map(this::toEntryNode)
					.toList();
			OffsetDateTime snapshotAt = entries.getFirst().getSnapshotAt().atOffset(KST_OFFSET);
			return new TopicExplorationResponse(snapshotAt, centerTopic, entryNodes);
		} catch (RuntimeException exception) {
			log.error("Topic별 탐색 데이터 조회 또는 응답 조합에 실패했습니다: topicCode={}", topicCode, exception);
			throw new BusinessException(TopicExplorationErrorCode.TOPIC_EXPLORATION_FETCH_FAILED, exception);
		}
	}

	private TopicExplorationResponse.EntryNode toEntryNode(TopicExplorationEntry entry) {
		return new TopicExplorationResponse.EntryNode(
				entry.getTopicExplorationEntryId(),
				entry.getRank(),
				entry.getNodeType(),
				entry.getNodeId(),
				entry.getNodeTitle(),
				entry.getArticleCount());
	}
}

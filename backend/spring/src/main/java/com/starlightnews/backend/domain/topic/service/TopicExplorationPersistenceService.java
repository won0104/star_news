package com.starlightnews.backend.domain.topic.service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;

import com.starlightnews.backend.domain.topic.domain.TopicExplorationEntry;
import com.starlightnews.backend.domain.topic.repository.TopicExplorationEntryRepository;
import com.starlightnews.backend.global.enums.TopicCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 계산이 끝난 Topic별 탐색 진입 Node 한 회차를 MySQL에 원자적으로 반영한다.
 */
@Service
@RequiredArgsConstructor
public class TopicExplorationPersistenceService {

	private static final int MAX_ENTRY_COUNT_PER_TOPIC = 10;

	private final TopicExplorationEntryRepository topicExplorationEntryRepository;

	/**
	 * 결과가 존재하는 Topic만 동일 공개 회차의 기존 행을 새 결과로 교체한다.
	 * 결과가 없는 Topic은 기존 최신 회차를 유지해야 하므로 입력 Map에 포함하지 않는다.
	 */
	@Transactional
	public void replaceSnapshot(
			LocalDateTime snapshotAt,
			Map<TopicCode, List<TopicExplorationEntry>> entriesByTopic
	) {
		Objects.requireNonNull(snapshotAt, "snapshotAt은 null일 수 없습니다.");
		Objects.requireNonNull(entriesByTopic, "entriesByTopic은 null일 수 없습니다.");
		if (entriesByTopic.isEmpty()) {
			throw new IllegalArgumentException("교체할 Topic별 탐색 결과가 비어 있습니다.");
		}

		List<TopicExplorationEntry> entriesToSave = new ArrayList<>();
		for (Map.Entry<TopicCode, List<TopicExplorationEntry>> topicEntries : entriesByTopic.entrySet()) {
			TopicCode topicCode = Objects.requireNonNull(topicEntries.getKey(), "topicCode는 null일 수 없습니다.");
			List<TopicExplorationEntry> entries = Objects.requireNonNull(
					topicEntries.getValue(), "Topic별 탐색 결과는 null일 수 없습니다.");
			validateEntries(snapshotAt, topicCode, entries);
			entriesToSave.addAll(entries);
		}

		for (TopicCode topicCode : entriesByTopic.keySet()) {
			topicExplorationEntryRepository.deleteAllByTopicCodeAndSnapshotAt(topicCode, snapshotAt);
		}
		topicExplorationEntryRepository.saveAll(entriesToSave);
	}

	private void validateEntries(
			LocalDateTime snapshotAt,
			TopicCode topicCode,
			List<TopicExplorationEntry> entries
	) {
		if (entries.isEmpty() || entries.size() > MAX_ENTRY_COUNT_PER_TOPIC) {
			throw new IllegalArgumentException("Topic별 탐색 결과는 회차당 1개 이상 10개 이하이어야 합니다.");
		}

		for (int index = 0; index < entries.size(); index++) {
			TopicExplorationEntry entry = Objects.requireNonNull(entries.get(index), "탐색 진입 항목은 null일 수 없습니다.");
			if (!snapshotAt.equals(entry.getSnapshotAt()) || topicCode != entry.getTopicCode()) {
				throw new IllegalArgumentException("공개 회차 또는 Topic이 다른 탐색 결과를 함께 저장할 수 없습니다.");
			}
			if (entry.getRank() != index + 1) {
				throw new IllegalArgumentException("Topic별 탐색 순위는 1부터 연속되어야 합니다.");
			}
		}
	}
}

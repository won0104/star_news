package com.starlightnews.backend.domain.topic.service;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.TimeUnit;

import com.starlightnews.backend.domain.topic.domain.TopicExplorationEntry;
import com.starlightnews.backend.domain.topic.repository.TopicExplorationAggregationRepository;
import com.starlightnews.backend.domain.topic.repository.TopicExplorationCandidate;
import com.starlightnews.backend.global.enums.TopicCode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * Neo4j에서 최근 24시간의 대표 Event를 Topic별로 집계하고 MySQL 저장 모델로 변환한다.
 * Neo4j 조회를 마친 뒤 저장 전용 서비스를 호출하여 MySQL 트랜잭션 범위를 짧게 유지한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TopicExplorationAggregationService {

	private static final int ENTRY_LIMIT_PER_TOPIC = 10;
	private static final int AGGREGATION_WINDOW_HOURS = 24;
	private static final ZoneId KST = ZoneId.of("Asia/Seoul");
	private static final List<TopicCode> SUPPORTED_TOPIC_CODES = List.of(TopicCode.values());

	private final TopicExplorationAggregationRepository topicExplorationAggregationRepository;
	private final TopicExplorationPersistenceService topicExplorationPersistenceService;

	/**
	 * aggregationAt 직전 24시간을 집계하여 다음 정각에 공개할 결과를 저장한다.
	 * 05:50 집계는 06:00, 17:50 집계는 18:00 공개 회차로 저장된다.
	 *
	 * @return 저장한 전체 Topic 탐색 진입 항목 수. 후보가 없으면 기존 결과를 유지하고 0을 반환한다.
	 */
	public int aggregate(OffsetDateTime aggregationAt) {
		Objects.requireNonNull(aggregationAt, "aggregationAt은 null일 수 없습니다.");

		long totalStartedAt = System.nanoTime();
		long queryStartedAt = System.nanoTime();
		List<TopicExplorationCandidate> candidates =
				topicExplorationAggregationRepository.findTopDistinctEventsByTopic(
						aggregationAt.minusHours(AGGREGATION_WINDOW_HOURS),
						aggregationAt,
						SUPPORTED_TOPIC_CODES,
						ENTRY_LIMIT_PER_TOPIC);
		long neo4jQueryDurationMs = elapsedMillis(queryStartedAt);

		if (candidates.isEmpty()) {
			log.warn("Topic별 탐색 집계 결과가 없어 기존 결과를 유지합니다: aggregationAt={}, neo4jQueryDurationMs={}",
					aggregationAt, neo4jQueryDurationMs);
			return 0;
		}

		LocalDateTime snapshotAt = resolveNextPublicationAt(aggregationAt);
		Map<TopicCode, List<TopicExplorationEntry>> entriesByTopic = toEntriesByTopic(candidates, snapshotAt);
		int entryCount = entriesByTopic.values().stream()
				.mapToInt(List::size)
				.sum();

		long writeStartedAt = System.nanoTime();
		topicExplorationPersistenceService.replaceSnapshot(snapshotAt, entriesByTopic);
		long mysqlWriteDurationMs = elapsedMillis(writeStartedAt);

		log.info(
				"Topic별 탐색 집계 완료: aggregationAt={}, snapshotAt={}, topicCount={}, entryCount={}, "
						+ "neo4jQueryDurationMs={}, mysqlWriteDurationMs={}, totalDurationMs={}",
				aggregationAt,
				snapshotAt,
				entriesByTopic.size(),
				entryCount,
				neo4jQueryDurationMs,
				mysqlWriteDurationMs,
				elapsedMillis(totalStartedAt));
		return entryCount;
	}

	private LocalDateTime resolveNextPublicationAt(OffsetDateTime aggregationAt) {
		return aggregationAt.atZoneSameInstant(KST)
				.plusHours(1)
				.withMinute(0)
				.withSecond(0)
				.withNano(0)
				.toLocalDateTime();
	}

	private Map<TopicCode, List<TopicExplorationEntry>> toEntriesByTopic(
			List<TopicExplorationCandidate> candidates,
			LocalDateTime snapshotAt
	) {
		Map<TopicCode, List<TopicExplorationEntry>> entriesByTopic = new EnumMap<>(TopicCode.class);
		for (TopicExplorationCandidate candidate : candidates) {
			validate(candidate);
			List<TopicExplorationEntry> topicEntries = entriesByTopic.computeIfAbsent(
					candidate.topicCode(), ignored -> new ArrayList<>());
			if (topicEntries.size() >= ENTRY_LIMIT_PER_TOPIC) {
				throw new IllegalStateException("Neo4j Topic별 탐색 집계 결과가 Topic당 최대 개수를 초과했습니다: topicCode="
						+ candidate.topicCode());
			}

			topicEntries.add(new TopicExplorationEntry(
					snapshotAt,
					candidate.topicCode(),
					candidate.nodeId(),
					candidate.nodeTitle(),
					topicEntries.size() + 1,
					Math.toIntExact(candidate.articleCount())));
		}
		return entriesByTopic;
	}

	private void validate(TopicExplorationCandidate candidate) {
		if (candidate == null) {
			throw new IllegalStateException("Topic별 탐색 후보는 null일 수 없습니다.");
		}
		if (candidate.topicCode() == null) {
			throw new IllegalStateException("Topic별 탐색 후보의 topicCode가 비어 있습니다.");
		}
		if (candidate.nodeId() == null || candidate.nodeId().isBlank()) {
			throw new IllegalStateException("Topic별 탐색 후보의 nodeId가 비어 있습니다: topicCode="
					+ candidate.topicCode());
		}
		if (candidate.nodeTitle() == null || candidate.nodeTitle().isBlank()) {
			throw new IllegalStateException("Topic별 탐색 후보의 nodeTitle이 비어 있습니다: nodeId="
					+ candidate.nodeId());
		}
		if (candidate.articleCount() <= 0) {
			throw new IllegalStateException("Topic별 탐색 후보의 articleCount는 양수여야 합니다: nodeId="
					+ candidate.nodeId());
		}
	}

	private long elapsedMillis(long startedAt) {
		return TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - startedAt);
	}
}

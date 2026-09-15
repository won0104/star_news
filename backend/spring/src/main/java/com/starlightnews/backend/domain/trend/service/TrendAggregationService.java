package com.starlightnews.backend.domain.trend.service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.concurrent.TimeUnit;

import com.starlightnews.backend.domain.trend.domain.Trend;
import com.starlightnews.backend.domain.trend.repository.TrendAggregationRepository;
import com.starlightnews.backend.domain.trend.repository.TrendCandidate;
import com.starlightnews.backend.global.enums.NodeType;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * Neo4j에서 최근 24시간의 대표 Event를 집계하고 MySQL 저장 모델로 변환한다.
 * Neo4j 조회를 마친 뒤 저장 전용 서비스를 호출하여 MySQL 트랜잭션 범위를 짧게 유지한다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TrendAggregationService {

	private static final int TREND_LIMIT = 10;
	private static final int AGGREGATION_WINDOW_HOURS = 24;
	private static final ZoneId KST = ZoneId.of("Asia/Seoul");

	private final TrendAggregationRepository trendAggregationRepository;
	private final TrendPersistenceService trendPersistenceService;

	/**
	 * 주어진 기준 시각 직전 24시간을 집계한다.
	 *
	 * @return 저장한 트렌드 항목 수. 후보가 없으면 기존 결과를 유지하고 0을 반환한다.
	 */
	public int aggregate(OffsetDateTime snapshotAt) {
		Objects.requireNonNull(snapshotAt, "snapshotAt은 null일 수 없습니다.");

		long totalStartedAt = System.nanoTime();
		long queryStartedAt = System.nanoTime();
		List<TrendCandidate> candidates = trendAggregationRepository.findTopDistinctEvents(
				snapshotAt.minusHours(AGGREGATION_WINDOW_HOURS), snapshotAt, TREND_LIMIT);
		long neo4jQueryDurationMs = elapsedMillis(queryStartedAt);

		if (candidates.isEmpty()) {
			log.warn("트렌드 집계 결과가 없어 기존 결과를 유지합니다: snapshotAt={}, neo4jQueryDurationMs={}",
					snapshotAt, neo4jQueryDurationMs);
			return 0;
		}
		if (candidates.size() > TREND_LIMIT) {
			throw new IllegalStateException("Neo4j 트렌드 집계 결과가 최대 개수를 초과했습니다.");
		}

		LocalDateTime storedSnapshotAt = snapshotAt.atZoneSameInstant(KST).toLocalDateTime();
		List<Trend> trends = toTrends(candidates, storedSnapshotAt);

		long writeStartedAt = System.nanoTime();
		trendPersistenceService.replaceSnapshot(storedSnapshotAt, trends);
		long mysqlWriteDurationMs = elapsedMillis(writeStartedAt);

		log.info(
				"트렌드 집계 완료: snapshotAt={}, selectedTrendCount={}, neo4jQueryDurationMs={}, "
						+ "mysqlWriteDurationMs={}, totalDurationMs={}",
				snapshotAt,
				trends.size(),
				neo4jQueryDurationMs,
				mysqlWriteDurationMs,
				elapsedMillis(totalStartedAt));
		return trends.size();
	}

	private List<Trend> toTrends(List<TrendCandidate> candidates, LocalDateTime snapshotAt) {
		List<Trend> trends = new ArrayList<>(candidates.size());
		for (int index = 0; index < candidates.size(); index++) {
			TrendCandidate candidate = candidates.get(index);
			validate(candidate);
			int articleCount = Math.toIntExact(candidate.articleCount());
			trends.add(new Trend(
					snapshotAt,
					NodeType.EVENT,
					candidate.nodeId(),
					candidate.nodeTitle(),
					index + 1,
					articleCount,
					BigDecimal.valueOf(articleCount)));
		}
		return List.copyOf(trends);
	}

	private void validate(TrendCandidate candidate) {
		if (candidate.nodeId() == null || candidate.nodeId().isBlank()) {
			throw new IllegalStateException("트렌드 후보의 nodeId가 비어 있습니다.");
		}
		if (candidate.nodeTitle() == null || candidate.nodeTitle().isBlank()) {
			throw new IllegalStateException("트렌드 후보의 nodeTitle이 비어 있습니다: nodeId=" + candidate.nodeId());
		}
		if (candidate.articleCount() <= 0) {
			throw new IllegalStateException("트렌드 후보의 articleCount는 양수여야 합니다: nodeId=" + candidate.nodeId());
		}
	}

	private long elapsedMillis(long startedAt) {
		return TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - startedAt);
	}
}

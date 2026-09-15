package com.starlightnews.backend.domain.trend.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;

import com.starlightnews.backend.domain.trend.domain.Trend;
import com.starlightnews.backend.domain.trend.repository.TrendRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 계산이 끝난 트렌드 한 회차를 MySQL에 원자적으로 반영한다.
 */
@Service
@RequiredArgsConstructor
public class TrendPersistenceService {

	private static final int MAX_TREND_COUNT = 10;

	private final TrendRepository trendRepository;

	/**
	 * 동일한 집계 기준 시각의 기존 결과를 새 결과로 교체한다.
	 * 빈 결과는 이전 트렌드를 유지해야 하므로 이 메서드의 입력으로 허용하지 않는다.
	 */
	@Transactional
	public void replaceSnapshot(LocalDateTime snapshotAt, List<Trend> trends) {
		Objects.requireNonNull(snapshotAt, "snapshotAt은 null일 수 없습니다.");
		Objects.requireNonNull(trends, "trends는 null일 수 없습니다.");
		if (trends.isEmpty() || trends.size() > MAX_TREND_COUNT) {
			throw new IllegalArgumentException("트렌드는 한 회차에 1개 이상 10개 이하이어야 합니다.");
		}

		trendRepository.deleteAllBySnapshotAt(snapshotAt);
		trendRepository.saveAll(trends);
	}
}

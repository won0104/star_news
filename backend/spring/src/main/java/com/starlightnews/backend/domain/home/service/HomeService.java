package com.starlightnews.backend.domain.home.service;

import java.time.Clock;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.home.dto.HomeResponse;
import com.starlightnews.backend.domain.home.exception.HomeErrorCode;
import com.starlightnews.backend.domain.trend.domain.Trend;
import com.starlightnews.backend.domain.trend.repository.TrendRepository;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * MySQL에 저장된 공개 시각이 지난 최신 트렌드를 홈 응답으로 변환한다.
 * 요청 시 집계하거나 Redis·Neo4j·사용자 데이터를 조회하지 않는다.
 */
@Slf4j
@Service
public class HomeService {

	private static final int TREND_LIMIT = 10;

	/** 집계 서비스가 DATETIME에 KST 벽시계로 저장한 시각에 오프셋을 붙인다. */
	private static final ZoneOffset KST = ZoneOffset.ofHours(9);

	private final TrendRepository trendRepository;
	private final Clock trendClock;

	public HomeService(TrendRepository trendRepository, @Qualifier("trendClock") Clock trendClock) {
		this.trendRepository = trendRepository;
		this.trendClock = trendClock;
	}

	@Transactional(readOnly = true)
	public HomeResponse getHome() {
		try {
			LocalDateTime now = LocalDateTime.ofInstant(trendClock.instant(), ZoneId.of("Asia/Seoul"));
			List<Trend> trends = trendRepository.findLatestTrends(now, PageRequest.of(0, TREND_LIMIT));
			if (trends.isEmpty()) {
				return new HomeResponse(null, List.of());
			}

			List<HomeResponse.Item> items = trends.stream().map(this::toItem).toList();
			return new HomeResponse(trends.getFirst().getSnapshotAt().atOffset(KST), items);
		} catch (RuntimeException exception) {
			log.error("홈 트렌드 데이터 조회 또는 응답 조합에 실패했습니다.", exception);
			throw new BusinessException(HomeErrorCode.HOME_DATA_FETCH_FAILED);
		}
	}

	private HomeResponse.Item toItem(Trend trend) {
		return new HomeResponse.Item(
				trend.getTrendItemId(),
				trend.getRank(),
				trend.getNodeType(),
				trend.getNodeId(),
				trend.getNodeTitle(),
				trend.getArticleCount());
	}
}

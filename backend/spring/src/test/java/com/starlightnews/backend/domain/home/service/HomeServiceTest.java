package com.starlightnews.backend.domain.home.service;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;

import com.starlightnews.backend.domain.home.dto.HomeResponse;
import com.starlightnews.backend.domain.home.exception.HomeErrorCode;
import com.starlightnews.backend.domain.trend.domain.Trend;
import com.starlightnews.backend.domain.trend.repository.TrendRepository;
import com.starlightnews.backend.global.enums.NodeType;
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

@ExtendWith(MockitoExtension.class)
class HomeServiceTest {

	private static final LocalDateTime SNAPSHOT_AT = LocalDateTime.of(2026, 9, 15, 18, 0);
	private static final LocalDateTime NOW = LocalDateTime.of(2026, 9, 15, 19, 0);
	private static final String NODE_ID = "00000020-0920-4000-8000-000000000001";

	@Mock
	private TrendRepository trendRepository;

	private HomeService homeService;

	@BeforeEach
	void setUp() {
		// UTC 시계를 주입해도 저장소 조회 기준은 KST 벽시계여야 한다.
		Clock clock = Clock.fixed(NOW.atOffset(ZoneOffset.ofHours(9)).toInstant(), ZoneOffset.UTC);
		homeService = new HomeService(trendRepository, clock);
	}

	@Test
	void 저장된_표시_정보를_변환하고_공개_시각에_KST_오프셋을_붙인다() {
		Trend first = trend(101L, 1, NODE_ID, "첫 번째 사건", 23);
		Trend second = trend(102L, 2, "00000020-0920-4000-8000-000000000002", "두 번째 사건", 12);
		given(trendRepository.findLatestTrends(NOW, PageRequest.of(0, 10))).willReturn(List.of(first, second));

		HomeResponse response = homeService.getHome();

		assertThat(response.snapshotAt()).isEqualTo(OffsetDateTime.parse("2026-09-15T18:00:00+09:00"));
		assertThat(response.trends()).containsExactly(
				new HomeResponse.Item(101L, 1, NodeType.EVENT, NODE_ID, "첫 번째 사건", 23),
				new HomeResponse.Item(102L, 2, NodeType.EVENT,
						"00000020-0920-4000-8000-000000000002", "두 번째 사건", 12));
		verify(trendRepository).findLatestTrends(NOW, PageRequest.of(0, 10));
	}

	@Test
	void 저장된_트렌드가_없으면_공개_시각은_null이고_목록은_빈_배열이다() {
		given(trendRepository.findLatestTrends(NOW, PageRequest.of(0, 10))).willReturn(List.of());

		HomeResponse response = homeService.getHome();

		assertThat(response.snapshotAt()).isNull();
		assertThat(response.trends()).isEmpty();
	}

	@Test
	void 조회_실패는_HOME_DATA_FETCH_FAILED로_변환한다() {
		given(trendRepository.findLatestTrends(NOW, PageRequest.of(0, 10)))
				.willThrow(new DataAccessResourceFailureException("DB 연결 실패"));

		assertHomeFetchFailed();
	}

	@Test
	void 응답_조합_실패도_HOME_DATA_FETCH_FAILED로_변환한다() {
		given(trendRepository.findLatestTrends(NOW, PageRequest.of(0, 10)))
				.willReturn(List.of(trend(null, 1, NODE_ID, "사건", 23)));

		assertHomeFetchFailed();
	}

	private void assertHomeFetchFailed() {
		assertThatThrownBy(homeService::getHome)
				.isInstanceOfSatisfying(BusinessException.class,
						exception -> assertThat(exception.getErrorCode())
								.isEqualTo(HomeErrorCode.HOME_DATA_FETCH_FAILED));
	}

	private Trend trend(Long id, int rank, String nodeId, String title, int articleCount) {
		Trend trend = new Trend(SNAPSHOT_AT, NodeType.EVENT, nodeId, title,
				rank, articleCount, BigDecimal.valueOf(articleCount));
		ReflectionTestUtils.setField(trend, "trendItemId", id);
		return trend;
	}
}

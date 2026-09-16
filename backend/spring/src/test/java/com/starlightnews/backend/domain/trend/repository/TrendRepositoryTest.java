package com.starlightnews.backend.domain.trend.repository;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.IntStream;

import com.starlightnews.backend.domain.trend.domain.Trend;
import com.starlightnews.backend.global.enums.NodeType;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class TrendRepositoryTest {

	private static final LocalDateTime PREVIOUS_AT = LocalDateTime.of(2026, 9, 14, 18, 0);
	private static final LocalDateTime LATEST_AT = LocalDateTime.of(2026, 9, 15, 6, 0);

	@Autowired
	private TrendRepository trendRepository;

	@Autowired
	private TestEntityManager entityManager;

	@Test
	void 최신_회차만_순위_오름차순으로_최대_10개_조회한다() {
		trendRepository.saveAll(List.of(trend(PREVIOUS_AT, 1)));
		trendRepository.saveAll(IntStream.iterate(12, rank -> rank - 1)
				.limit(12)
				.mapToObj(rank -> trend(LATEST_AT, rank))
				.toList());
		entityManager.flush();
		entityManager.clear();

		List<Trend> found = trendRepository.findLatestTrends(LATEST_AT, PageRequest.of(0, 10));

		assertThat(found).hasSize(10);
		assertThat(found).extracting(Trend::getSnapshotAt).containsOnly(LATEST_AT);
		assertThat(found).extracting(Trend::getRank).containsExactly(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
		assertThat(found).extracting(Trend::getNodeTitle).startsWith("사건 1", "사건 2");
	}

	@Test
	void 저장된_트렌드가_없으면_빈_목록을_반환한다() {
		assertThat(trendRepository.findLatestTrends(LATEST_AT, PageRequest.of(0, 10))).isEmpty();
	}

	@Test
	void 공개_직전에는_이전_회차를_조회하고_정각부터_새_회차를_조회한다() {
		trendRepository.saveAll(List.of(trend(PREVIOUS_AT, 1), trend(LATEST_AT, 1)));
		entityManager.flush();
		entityManager.clear();

		LocalDateTime publishAt = LATEST_AT;
		assertThat(trendRepository.findLatestTrends(publishAt.minusNanos(1000), PageRequest.of(0, 10)))
				.extracting(Trend::getSnapshotAt).containsExactly(PREVIOUS_AT);
		assertThat(trendRepository.findLatestTrends(publishAt, PageRequest.of(0, 10)))
				.extracting(Trend::getSnapshotAt).containsExactly(LATEST_AT);
	}

	@Test
	void 미공개_회차만_있으면_빈_목록을_반환한다() {
		trendRepository.saveAll(List.of(trend(LATEST_AT, 1)));
		entityManager.flush();
		entityManager.clear();

		assertThat(trendRepository.findLatestTrends(LATEST_AT.minusHours(1), PageRequest.of(0, 10))).isEmpty();
	}

	@Test
	void 다음_회차가_없으면_공개_시각이_지나도_이전_결과를_유지한다() {
		trendRepository.saveAll(List.of(trend(PREVIOUS_AT, 1)));
		entityManager.flush();
		entityManager.clear();

		assertThat(trendRepository.findLatestTrends(LATEST_AT.plusHours(2), PageRequest.of(0, 10)))
				.extracting(Trend::getSnapshotAt).containsExactly(PREVIOUS_AT);
	}

	@Test
	void 저녁_공개_시각에도_오전_회차에서_저녁_회차로_전환한다() {
		LocalDateTime eveningAt = LATEST_AT.withHour(18);
		trendRepository.saveAll(List.of(trend(LATEST_AT, 1), trend(eveningAt, 1)));
		entityManager.flush();
		entityManager.clear();

		assertThat(trendRepository.findLatestTrends(eveningAt.minusSeconds(1), PageRequest.of(0, 10)))
				.extracting(Trend::getSnapshotAt).containsExactly(LATEST_AT);
		assertThat(trendRepository.findLatestTrends(eveningAt, PageRequest.of(0, 10)))
				.extracting(Trend::getSnapshotAt).containsExactly(eveningAt);
	}

	private Trend trend(LocalDateTime snapshotAt, int rank) {
		return new Trend(
				snapshotAt,
				NodeType.EVENT,
				String.format("00000020-0920-4000-8000-%012d", rank),
				"사건 " + rank,
				rank,
				20 - rank,
				BigDecimal.valueOf(20 - rank));
	}
}

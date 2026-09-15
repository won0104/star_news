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

		List<Trend> found = trendRepository.findLatestTrends(PageRequest.of(0, 10));

		assertThat(found).hasSize(10);
		assertThat(found).extracting(Trend::getSnapshotAt).containsOnly(LATEST_AT);
		assertThat(found).extracting(Trend::getRank).containsExactly(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
		assertThat(found).extracting(Trend::getNodeTitle).startsWith("사건 1", "사건 2");
	}

	@Test
	void 저장된_트렌드가_없으면_빈_목록을_반환한다() {
		assertThat(trendRepository.findLatestTrends(PageRequest.of(0, 10))).isEmpty();
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

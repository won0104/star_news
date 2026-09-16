package com.starlightnews.backend.domain.trend.service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.trend.domain.Trend;
import com.starlightnews.backend.domain.trend.repository.TrendRepository;
import com.starlightnews.backend.global.enums.NodeType;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(TrendPersistenceService.class)
class TrendPersistenceServiceTest {

	private static final LocalDateTime PREVIOUS_AT = LocalDateTime.of(2026, 9, 14, 18, 0);
	private static final LocalDateTime SNAPSHOT_AT = LocalDateTime.of(2026, 9, 15, 6, 0);
	private static final String PREVIOUS_NODE_ID = "00000020-0920-4000-8000-000000000001";
	private static final String OLD_NODE_ID = "00000020-0920-4000-8000-000000000002";
	private static final String NEW_NODE_ID_1 = "00000020-0920-4000-8000-000000000003";
	private static final String NEW_NODE_ID_2 = "00000020-0920-4000-8000-000000000004";

	@Autowired
	private TrendPersistenceService trendPersistenceService;

	@Autowired
	private TrendRepository trendRepository;

	@Autowired
	private TestEntityManager entityManager;

	@Test
	void 동일_회차만_교체하고_과거_회차는_유지한다() {
		trendRepository.saveAll(List.of(
				trend(PREVIOUS_AT, PREVIOUS_NODE_ID, 1, 5),
				trend(SNAPSHOT_AT, OLD_NODE_ID, 1, 4)));
		entityManager.flush();
		entityManager.clear();

		trendPersistenceService.replaceSnapshot(SNAPSHOT_AT, List.of(
				trend(SNAPSHOT_AT, NEW_NODE_ID_1, 1, 10),
				trend(SNAPSHOT_AT, NEW_NODE_ID_2, 2, 8)));
		entityManager.flush();
		entityManager.clear();

		List<Trend> stored = entityManager.getEntityManager()
				.createQuery("SELECT t FROM Trend t ORDER BY t.snapshotAt, t.rank", Trend.class)
				.getResultList();
		assertThat(stored).extracting(Trend::getNodeId)
				.containsExactly(PREVIOUS_NODE_ID, NEW_NODE_ID_1, NEW_NODE_ID_2);
	}

	@Test
	void 빈_결과나_10개_초과_결과는_거부한다() {
		assertThatThrownBy(() -> trendPersistenceService.replaceSnapshot(SNAPSHOT_AT, List.of()))
				.isInstanceOf(IllegalArgumentException.class);

		List<Trend> tooMany = java.util.stream.IntStream.rangeClosed(1, 11)
				.mapToObj(rank -> trend(
						SNAPSHOT_AT,
						String.format("00000020-0920-4000-8000-%012d", rank),
						rank,
						rank))
				.toList();
		assertThatThrownBy(() -> trendPersistenceService.replaceSnapshot(SNAPSHOT_AT, tooMany))
				.isInstanceOf(IllegalArgumentException.class);
	}

	private Trend trend(LocalDateTime snapshotAt, String nodeId, int rank, int articleCount) {
		return new Trend(
				snapshotAt,
				NodeType.EVENT,
				nodeId,
				"사건 " + nodeId,
				rank,
				articleCount,
				BigDecimal.valueOf(articleCount));
	}
}

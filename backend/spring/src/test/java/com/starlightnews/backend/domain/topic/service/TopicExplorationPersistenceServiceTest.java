package com.starlightnews.backend.domain.topic.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.topic.domain.TopicExplorationEntry;
import com.starlightnews.backend.domain.topic.repository.TopicExplorationEntryRepository;
import com.starlightnews.backend.global.enums.TopicCode;
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
@Import(TopicExplorationPersistenceService.class)
class TopicExplorationPersistenceServiceTest {

	private static final LocalDateTime PREVIOUS_AT = LocalDateTime.of(2026, 9, 23, 18, 0);
	private static final LocalDateTime SNAPSHOT_AT = LocalDateTime.of(2026, 9, 24, 6, 0);

	@Autowired
	private TopicExplorationPersistenceService topicExplorationPersistenceService;

	@Autowired
	private TopicExplorationEntryRepository topicExplorationEntryRepository;

	@Autowired
	private TestEntityManager entityManager;

	@Test
	void 결과가_있는_Topic의_동일_회차만_교체하고_다른_Topic과_과거_회차는_유지한다() {
		topicExplorationEntryRepository.saveAll(List.of(
				entry(PREVIOUS_AT, TopicCode.ECONOMY, "previous-economy", 1),
				entry(SNAPSHOT_AT, TopicCode.ECONOMY, "old-economy", 1),
				entry(SNAPSHOT_AT, TopicCode.SOCIETY, "current-society", 1)));
		entityManager.flush();
		entityManager.clear();

		List<TopicExplorationEntry> newEconomyEntries = List.of(
				entry(SNAPSHOT_AT, TopicCode.ECONOMY, "new-economy-1", 1),
				entry(SNAPSHOT_AT, TopicCode.ECONOMY, "new-economy-2", 2));
		topicExplorationPersistenceService.replaceSnapshot(
				SNAPSHOT_AT,
				Map.of(TopicCode.ECONOMY, newEconomyEntries));
		entityManager.flush();
		entityManager.clear();

		List<TopicExplorationEntry> stored = entityManager.getEntityManager()
				.createQuery("""
						SELECT entry FROM TopicExplorationEntry entry
						ORDER BY entry.snapshotAt, entry.topicCode, entry.rank
						""", TopicExplorationEntry.class)
				.getResultList();
		assertThat(stored).extracting(TopicExplorationEntry::getNodeId)
				.containsExactly("previous-economy", "new-economy-1", "new-economy-2", "current-society");
	}

	@Test
	void 빈_결과와_연속되지_않은_순위는_거부한다() {
		assertThatThrownBy(() -> topicExplorationPersistenceService.replaceSnapshot(SNAPSHOT_AT, Map.of()))
				.isInstanceOf(IllegalArgumentException.class);

		List<TopicExplorationEntry> invalidRanks = List.of(
				entry(SNAPSHOT_AT, TopicCode.ECONOMY, "economy-1", 1),
				entry(SNAPSHOT_AT, TopicCode.ECONOMY, "economy-2", 3));
		assertThatThrownBy(() -> topicExplorationPersistenceService.replaceSnapshot(
				SNAPSHOT_AT, Map.of(TopicCode.ECONOMY, invalidRanks)))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessageContaining("순위");
	}

	private TopicExplorationEntry entry(
			LocalDateTime snapshotAt,
			TopicCode topicCode,
			String nodeId,
			int rank
	) {
		return new TopicExplorationEntry(
				snapshotAt,
				topicCode,
				nodeId,
				topicCode.labelKo() + " 사건 " + rank,
				rank,
				20 - rank);
	}
}

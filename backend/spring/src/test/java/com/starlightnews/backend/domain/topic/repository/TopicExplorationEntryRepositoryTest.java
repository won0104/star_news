package com.starlightnews.backend.domain.topic.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.topic.domain.TopicExplorationEntry;
import com.starlightnews.backend.global.enums.TopicCode;
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
class TopicExplorationEntryRepositoryTest {

	private static final LocalDateTime PREVIOUS_AT = LocalDateTime.of(2026, 9, 23, 18, 0);
	private static final LocalDateTime LATEST_AT = LocalDateTime.of(2026, 9, 24, 6, 0);
	private static final LocalDateTime FUTURE_AT = LocalDateTime.of(2026, 9, 24, 18, 0);

	@Autowired
	private TopicExplorationEntryRepository topicExplorationEntryRepository;

	@Autowired
	private TestEntityManager entityManager;

	@Test
	void 선택한_Topic에서_공개된_최신_회차만_순위순으로_조회한다() {
		topicExplorationEntryRepository.saveAll(List.of(
				entry(PREVIOUS_AT, TopicCode.ECONOMY, 1),
				entry(LATEST_AT, TopicCode.ECONOMY, 2),
				entry(LATEST_AT, TopicCode.ECONOMY, 1),
				entry(FUTURE_AT, TopicCode.ECONOMY, 1),
				entry(LATEST_AT, TopicCode.SOCIETY, 1)));
		entityManager.flush();
		entityManager.clear();

		List<TopicExplorationEntry> found = topicExplorationEntryRepository.findLatestEntries(
				TopicCode.ECONOMY,
				LATEST_AT,
				PageRequest.of(0, 10));

		assertThat(found).hasSize(2);
		assertThat(found).extracting(TopicExplorationEntry::getTopicCode).containsOnly(TopicCode.ECONOMY);
		assertThat(found).extracting(TopicExplorationEntry::getSnapshotAt).containsOnly(LATEST_AT);
		assertThat(found).extracting(TopicExplorationEntry::getRank).containsExactly(1, 2);
	}

	@Test
	void 새_회차_공개_직전에는_이전_회차를_유지하고_정각부터_전환한다() {
		topicExplorationEntryRepository.saveAll(List.of(
				entry(PREVIOUS_AT, TopicCode.ECONOMY, 1),
				entry(LATEST_AT, TopicCode.ECONOMY, 1)));
		entityManager.flush();
		entityManager.clear();

		assertThat(topicExplorationEntryRepository.findLatestEntries(
				TopicCode.ECONOMY, LATEST_AT.minusNanos(1000), PageRequest.of(0, 10)))
				.extracting(TopicExplorationEntry::getSnapshotAt)
				.containsExactly(PREVIOUS_AT);
		assertThat(topicExplorationEntryRepository.findLatestEntries(
				TopicCode.ECONOMY, LATEST_AT, PageRequest.of(0, 10)))
				.extracting(TopicExplorationEntry::getSnapshotAt)
				.containsExactly(LATEST_AT);
	}

	private TopicExplorationEntry entry(LocalDateTime snapshotAt, TopicCode topicCode, int rank) {
		return new TopicExplorationEntry(
				snapshotAt,
				topicCode,
				String.format("00000020-0920-4000-%04d-%012d", topicCode.ordinal(), rank),
				topicCode.labelKo() + " 사건 " + rank,
				rank,
				20 - rank);
	}
}

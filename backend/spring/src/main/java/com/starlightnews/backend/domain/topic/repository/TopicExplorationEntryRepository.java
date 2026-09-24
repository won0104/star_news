package com.starlightnews.backend.domain.topic.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.topic.domain.TopicExplorationEntry;
import com.starlightnews.backend.global.enums.TopicCode;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * Topic별 탐색 진입 Node 저장소.
 * 같은 Topic과 공개 회차의 재집계 결과는 교체하고, 조회 시에는 이미 공개된 최신 회차만 반환한다.
 */
public interface TopicExplorationEntryRepository extends Repository<TopicExplorationEntry, Long> {

	@Query("""
			SELECT entry FROM TopicExplorationEntry entry
			WHERE entry.topicCode = :topicCode
			  AND entry.snapshotAt = (
			      SELECT MAX(latest.snapshotAt)
			      FROM TopicExplorationEntry latest
			      WHERE latest.topicCode = :topicCode
			        AND latest.snapshotAt <= :now
			  )
			ORDER BY entry.rank ASC
			""")
	List<TopicExplorationEntry> findLatestEntries(
			@Param("topicCode") TopicCode topicCode,
			@Param("now") LocalDateTime now,
			Pageable pageable
	);

	@Modifying(flushAutomatically = true, clearAutomatically = true)
	@Query("""
			DELETE FROM TopicExplorationEntry entry
			WHERE entry.topicCode = :topicCode
			  AND entry.snapshotAt = :snapshotAt
			""")
	int deleteAllByTopicCodeAndSnapshotAt(
			@Param("topicCode") TopicCode topicCode,
			@Param("snapshotAt") LocalDateTime snapshotAt
	);

	List<TopicExplorationEntry> saveAll(Iterable<TopicExplorationEntry> entries);
}

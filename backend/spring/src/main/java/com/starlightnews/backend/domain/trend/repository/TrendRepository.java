package com.starlightnews.backend.domain.trend.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.trend.domain.Trend;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 트렌드 집계 결과 저장소. 같은 공개 회차의 재실행 결과는 기존 행을 교체한다.
 * 홈 조회에서는 공개 시각이 지난 최신 집계 회차의 항목만 순위순으로 반환한다.
 */
public interface TrendRepository extends Repository<Trend, Long> {

	@Query("""
			SELECT t FROM Trend t
			WHERE t.snapshotAt = (
			      SELECT MAX(latest.snapshotAt) FROM Trend latest WHERE latest.snapshotAt <= :now
			  )
			ORDER BY t.rank ASC
			""")
	List<Trend> findLatestTrends(@Param("now") LocalDateTime now, Pageable pageable);

	@Modifying(flushAutomatically = true, clearAutomatically = true)
	@Query("DELETE FROM Trend t WHERE t.snapshotAt = :snapshotAt")
	int deleteAllBySnapshotAt(@Param("snapshotAt") LocalDateTime snapshotAt);

	List<Trend> saveAll(Iterable<Trend> trends);
}

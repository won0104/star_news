package com.starlightnews.backend.domain.trend.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.trend.domain.Trend;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

/**
 * 트렌드 집계 결과 저장소. 같은 집계 기준 시각의 재실행 결과는 기존 행을 교체한다.
 */
public interface TrendRepository extends Repository<Trend, Long> {

	@Modifying(flushAutomatically = true, clearAutomatically = true)
	@Query("DELETE FROM Trend t WHERE t.snapshotAt = :snapshotAt")
	int deleteAllBySnapshotAt(@Param("snapshotAt") LocalDateTime snapshotAt);

	List<Trend> saveAll(Iterable<Trend> trends);
}

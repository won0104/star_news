package com.starlightnews.backend.domain.recommendation.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationRunStatus;
import com.starlightnews.backend.domain.recommendation.domain.UserRecommendation;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

/**
 * 사용자별 회차 추천 결과 저장. ({@code user_recommendations})
 */
public interface UserRecommendationRepository extends JpaRepository<UserRecommendation, Long> {

	/**
	 * 해당 사용자들의 이번 회차 결과를 지운다.
	 *
	 * <p>회차를 다시 저장하기 전에 비우는 용도다. 유형을 가리지 않고 회차 단위로 통째로 지운다.
	 * 유형별로 나누면 한 유형만 새로 저장되고 다른 유형은 이전 회차가 남는 상태가 생긴다.
	 */
	@Modifying
	@Query("DELETE FROM UserRecommendation r WHERE r.userId IN :userIds AND r.availableAt = :availableAt")
	int deleteCycle(@Param("userIds") Collection<Long> userIds,
			@Param("availableAt") LocalDateTime availableAt);

	/**
	 * 공개 시각이 기준보다 오래된 회차를 지운다.
	 *
	 * <p>회차가 하루 두 번 쌓이므로 보관 기간을 넘긴 것은 정리한다.
	 */
	@Modifying
	@Query("DELETE FROM UserRecommendation r WHERE r.availableAt < :threshold")
	int deleteOlderThan(@Param("threshold") LocalDateTime threshold);

	List<UserRecommendation> findByUserIdAndAvailableAtOrderByRankAsc(Long userId, LocalDateTime availableAt);

	/**
	 * 사용자에게 공개된 회차 중 가장 최근 것의 공개 시각.
	 *
	 * <p>공개 시각이 아직 오지 않은 회차는 고르지 않는다. 계산은 05:30·17:30 에 끝나지만 공개는
	 * 06:00·18:00 이라, 그 사이에 조회하면 직전 회차가 보여야 한다.
	 *
	 * <p>실행이 끝난 회차만 고른다. 공개 시각이 지났어도 아직 도는 중이거나 실패한 회차는 일부
	 * 사용자만 저장돼 있거나 중간 상태라 직전 회차를 보여 준다. 같은 공개 시각으로 여러 번 돌았다면
	 * 하나라도 끝났으면 보여 준다.
	 *
	 * @param visible 보여 줄 실행 상태. {@code COMPLETED}·{@code PARTIAL}
	 */
	@Query("SELECT MAX(r.availableAt) FROM UserRecommendation r "
			+ "WHERE r.userId = :userId AND r.availableAt <= :now "
			+ "AND EXISTS (SELECT 1 FROM RecommendationRun run "
			+ "WHERE run.availableAt = r.availableAt AND run.status IN :visible)")
	Optional<LocalDateTime> findLatestAvailableAt(@Param("userId") Long userId,
			@Param("now") LocalDateTime now,
			@Param("visible") Collection<RecommendationRunStatus> visible);

	/**
	 * 한 회차의 추천을 순위 순으로 전부 조회한다.
	 *
	 * <p>나눠 보내지 않는다. 한 회차에 담기는 추천이 사용자당
	 * {@code app.recommendation.limit-per-user} 개(기본 10, 최대 50)뿐이라 한 화면에 들어간다.
	 *
	 * <p>순위가 같으면 PK 로 순서를 정한다. 한 사용자의 한 회차는 한 유형이라 지금은 순위가 겹치지
	 * 않지만, 유니크 제약이 유형까지 묶여 있어 DB 가 겹침을 막아 주지 않는다. 겹쳐도 회차마다 같은
	 * 차례로 보이게 둔다.
	 */
	@Query("SELECT r FROM UserRecommendation r "
			+ "WHERE r.userId = :userId AND r.availableAt = :availableAt "
			+ "ORDER BY r.rank ASC, r.userRecommendationId ASC")
	List<UserRecommendation> findCycle(@Param("userId") Long userId,
			@Param("availableAt") LocalDateTime availableAt);

	/**
	 * 한 회차에 실제로 추천된 Event 를 중복 없이 조회한다.
	 *
	 * <p>Event 는 사용자 사이에 공유되므로 사용자 수보다 훨씬 적다. 요약 생성 대상을 고를 때 쓴다.
	 */
	@Query("SELECT DISTINCT r.eventId FROM UserRecommendation r WHERE r.availableAt = :availableAt")
	List<String> findEventIdsByAvailableAt(@Param("availableAt") LocalDateTime availableAt);
}

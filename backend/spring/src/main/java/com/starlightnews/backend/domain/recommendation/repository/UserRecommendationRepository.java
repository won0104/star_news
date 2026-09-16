package com.starlightnews.backend.domain.recommendation.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

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
	 */
	@Query("SELECT MAX(r.availableAt) FROM UserRecommendation r "
			+ "WHERE r.userId = :userId AND r.availableAt <= :now")
	Optional<LocalDateTime> findLatestAvailableAt(@Param("userId") Long userId,
			@Param("now") LocalDateTime now);

	/**
	 * 한 회차의 추천을 순위 순으로 전부 조회한다.
	 *
	 * <p>나눠 보내지 않는다. 한 회차에 담기는 추천이 사용자당
	 * {@code app.recommendation.limit-per-user} 개(기본 10, 최대 50)뿐이라 한 화면에 들어간다.
	 *
	 * <p>{@code rank} 는 유형 안에서만 유일해서 한 회차에 같은 순위가 여러 번 나온다. 순위가
	 * 같으면 PK 로 순서를 정해 회차마다 같은 차례로 보이게 한다.
	 */
	@Query("SELECT r FROM UserRecommendation r "
			+ "WHERE r.userId = :userId AND r.availableAt = :availableAt "
			+ "ORDER BY r.rank ASC, r.userRecommendationId ASC")
	List<UserRecommendation> findCycle(@Param("userId") Long userId,
			@Param("availableAt") LocalDateTime availableAt);
}

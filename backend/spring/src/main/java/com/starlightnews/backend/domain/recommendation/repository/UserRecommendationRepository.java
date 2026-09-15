package com.starlightnews.backend.domain.recommendation.repository;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;

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
}

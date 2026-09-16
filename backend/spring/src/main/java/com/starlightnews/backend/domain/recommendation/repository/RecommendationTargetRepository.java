package com.starlightnews.backend.domain.recommendation.repository;

import java.util.List;

import com.starlightnews.backend.domain.user.domain.User;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;

/**
 * 추천을 계산할 사용자를 고른다.
 *
 * <p>사용자 그래프 동기화에도 같은 모양의 조회가 있지만 따로 둔다. 추천은 계산이 무거워서
 * (사용자마다 유사 사용자 탐색·벡터 검색) 나중에 "최근 접속자만" 처럼 대상을 좁힐 여지가 있다.
 * 그때 한쪽만 바꾸려면 기준이 나뉘어 있어야 한다.
 */
public interface RecommendationTargetRepository extends Repository<User, Long> {

	/**
	 * 추천 대상 사용자 ID 를 오름차순으로 한 페이지 조회한다.
	 *
	 * <p>지금은 탈퇴하지 않은 전체 사용자다.
	 */
	@Query(value = """
			SELECT user_id
			FROM users
			WHERE deleted_at IS NULL
			ORDER BY user_id
			""", nativeQuery = true)
	List<Long> findTargetUserIds(Pageable pageable);
}

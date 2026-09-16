package com.starlightnews.backend.domain.recommendation.repository;

import com.starlightnews.backend.support.TestFixtures;
import org.junit.jupiter.api.BeforeEach;
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
class RecommendationTargetRepositoryTest {

	@Autowired
	private RecommendationTargetRepository repository;

	@Autowired
	private TestEntityManager entityManager;

	@BeforeEach
	void insertUsers() {
		TestFixtures.insertUsers(entityManager, 1L, 2L, 3L);
	}

	private void softDelete(long userId) {
		entityManager.getEntityManager()
				.createNativeQuery("UPDATE users SET deleted_at = NOW(6) WHERE user_id = ?1")
				.setParameter(1, userId)
				.executeUpdate();
		entityManager.flush();
	}

	@Test
	void 추천_대상은_사용자ID_오름차순이다() {
		assertThat(repository.findTargetUserIds(PageRequest.of(0, 10)))
				.containsExactly(1L, 2L, 3L);
	}

	@Test
	void 탈퇴한_사용자는_추천_대상에서_제외한다() {
		softDelete(2L);

		assertThat(repository.findTargetUserIds(PageRequest.of(0, 10)))
				.containsExactly(1L, 3L);
	}

	@Test
	void 대상을_묶음_단위로_끊어_읽는다() {
		// 한 요청에 전체 사용자를 담지 않고 나눠 보내기 위한 조회다.
		assertThat(repository.findTargetUserIds(PageRequest.of(0, 2))).containsExactly(1L, 2L);
		assertThat(repository.findTargetUserIds(PageRequest.of(1, 2))).containsExactly(3L);
	}

	@Test
	void 마지막_페이지를_넘어서면_비어_있다() {
		// 배치가 이 신호로 반복을 끝낸다.
		assertThat(repository.findTargetUserIds(PageRequest.of(2, 2))).isEmpty();
	}
}

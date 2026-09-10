package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;

import com.starlightnews.backend.domain.user.domain.UserNodeFavorite;
import com.starlightnews.backend.domain.user.domain.UserNodeFavoriteId;
import com.starlightnews.backend.global.enums.NodeType;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class UserNodeFavoriteRepositoryTest {

	@Autowired
	private UserNodeFavoriteRepository repository;

	@Autowired
	private TestEntityManager entityManager;

	private void saveFavorite(long userId, NodeType nodeType, String nodeId) {
		entityManager.persist(new UserNodeFavorite(
				new UserNodeFavoriteId(userId, nodeType, nodeId), LocalDateTime.now()));
		entityManager.flush();
	}

	@Test
	void 즐겨찾기한_노드는_존재로_조회된다() {
		saveFavorite(1L, NodeType.EVENT, "node-uuid");

		assertThat(repository.existsById(new UserNodeFavoriteId(1L, NodeType.EVENT, "node-uuid"))).isTrue();
	}

	@Test
	void 즐겨찾기하지_않은_노드는_false다() {
		assertThat(repository.existsById(new UserNodeFavoriteId(1L, NodeType.EVENT, "none"))).isFalse();
	}

	@Test
	void 유저_타입_nodeId_중_하나라도_다르면_별개다() {
		saveFavorite(1L, NodeType.EVENT, "n1");

		assertThat(repository.existsById(new UserNodeFavoriteId(2L, NodeType.EVENT, "n1"))).isFalse();
		assertThat(repository.existsById(new UserNodeFavoriteId(1L, NodeType.STORY, "n1"))).isFalse();
		assertThat(repository.existsById(new UserNodeFavoriteId(1L, NodeType.EVENT, "n2"))).isFalse();
	}
}

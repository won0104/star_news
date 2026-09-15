package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.user.domain.UserNodeFavorite;
import com.starlightnews.backend.domain.user.domain.UserNodeFavoriteId;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.support.TestFixtures;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.PageRequest;
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

	@BeforeEach
	void insertReferencedRows() {
		TestFixtures.insertUsers(entityManager, 1L, 2L);
	}

	private void saveFavorite(long userId, NodeType nodeType, String nodeId) {
		saveFavorite(userId, nodeType, nodeId, LocalDateTime.now());
	}

	private void saveFavorite(long userId, NodeType nodeType, String nodeId, LocalDateTime favoritedAt) {
		entityManager.persist(new UserNodeFavorite(
				new UserNodeFavoriteId(userId, nodeType, nodeId), favoritedAt));
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

	@Test
	void 허용된_Node를_등록시각_DESC_유형과_ID_ASC로_조회한다() {
		String entityLow = "00000000-0000-0000-0000-000000000001";
		String entityHigh = "00000000-0000-0000-0000-000000000002";
		String eventId = "00000000-0000-0000-0000-000000000003";
		String articleId = "00000000-0000-0000-0000-000000000004";
		LocalDateTime sameTime = LocalDateTime.of(2026, 9, 14, 9, 0);
		saveFavorite(1L, NodeType.EVENT, eventId, sameTime);
		saveFavorite(1L, NodeType.ENTITY, entityHigh, sameTime);
		saveFavorite(1L, NodeType.ENTITY, entityLow, sameTime);
		saveFavorite(1L, NodeType.ARTICLE, articleId, sameTime.plusHours(1));
		saveFavorite(2L, NodeType.ENTITY, entityLow, sameTime.plusHours(2));

		List<UserNodeFavoriteRepository.NodeFavoriteRow> rows = repository.findFirstNodeFavoritePage(
				1L, List.of("ENTITY", "EVENT", "STATEMENT", "STORY"), PageRequest.of(0, 10));

		assertThat(rows).extracting(UserNodeFavoriteRepository.NodeFavoriteRow::getNodeId)
				.containsExactly(entityLow, entityHigh, eventId);
		assertThat(rows).extracting(UserNodeFavoriteRepository.NodeFavoriteRow::getNodeType)
				.containsExactly("ENTITY", "ENTITY", "EVENT");
		assertThat(rows).extracting(UserNodeFavoriteRepository.NodeFavoriteRow::getBookmarkedAt)
				.containsOnly(sameTime);
	}

	@Test
	void Node다음페이지는_복합커서보다_뒤의_항목만_조회한다() {
		String lowerId = "00000000-0000-0000-0000-000000000001";
		String cursorId = "00000000-0000-0000-0000-000000000002";
		String higherId = "00000000-0000-0000-0000-000000000003";
		String eventId = "00000000-0000-0000-0000-000000000004";
		LocalDateTime sameTime = LocalDateTime.of(2026, 9, 14, 9, 0);
		saveFavorite(1L, NodeType.ENTITY, lowerId, sameTime);
		saveFavorite(1L, NodeType.ENTITY, cursorId, sameTime);
		saveFavorite(1L, NodeType.ENTITY, higherId, sameTime);
		saveFavorite(1L, NodeType.EVENT, eventId, sameTime);

		List<UserNodeFavoriteRepository.NodeFavoriteRow> rows = repository.findNextNodeFavoritePage(
				1L,
				List.of("ENTITY", "EVENT", "STATEMENT", "STORY"),
				sameTime,
				"ENTITY",
				cursorId,
				PageRequest.of(0, 10));

		assertThat(rows).extracting(UserNodeFavoriteRepository.NodeFavoriteRow::getNodeId)
				.containsExactly(higherId, eventId);
	}

	@Test
	void 복합키_목록으로_즐겨찾기를_조회하고_선택한_항목만_삭제한다() {
		UserNodeFavoriteId entityId = new UserNodeFavoriteId(
				1L, NodeType.ENTITY, "00000000-0000-0000-0000-000000000001");
		UserNodeFavoriteId eventId = new UserNodeFavoriteId(
				1L, NodeType.EVENT, "00000000-0000-0000-0000-000000000002");
		repository.saveAll(List.of(
				new UserNodeFavorite(entityId, LocalDateTime.of(2026, 9, 14, 9, 0)),
				new UserNodeFavorite(eventId, LocalDateTime.of(2026, 9, 14, 10, 0))));
		repository.flush();
		entityManager.clear();

		assertThat(repository.findAllById(List.of(entityId, eventId)))
				.extracting(UserNodeFavorite::getId)
				.containsExactlyInAnyOrder(entityId, eventId);

		repository.deleteAllByIdInBatch(List.of(eventId));
		repository.flush();
		entityManager.clear();

		assertThat(repository.existsById(entityId)).isTrue();
		assertThat(repository.existsById(eventId)).isFalse();
	}
}

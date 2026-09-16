package com.starlightnews.backend.domain.usergraph.repository;

import java.time.LocalDateTime;
import java.util.List;

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
import static org.assertj.core.api.Assertions.tuple;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class UserGraphAggregationRepositoryTest {

	private static final List<String> INTEREST_NODE_TYPES = List.of("ENTITY", "STORY");

	private static final String ENTITY_ID = "00000126-0001-4000-8000-000000000001";
	private static final String STORY_ID = "00000126-0002-4000-8000-000000000002";
	private static final String EVENT_ID = "00000126-0003-4000-8000-000000000003";
	private static final String OTHER_EVENT_ID = "00000126-0004-4000-8000-000000000004";

	@Autowired
	private UserGraphAggregationRepository repository;

	@Autowired
	private TestEntityManager entityManager;

	@BeforeEach
	void insertUsers() {
		TestFixtures.insertUsers(entityManager, 1L, 2L, 3L);
	}

	private void insertNodeFavorite(long userId, String nodeType, String nodeId) {
		entityManager.getEntityManager()
				.createNativeQuery("INSERT INTO user_node_favorites (user_id, node_type, node_id) "
						+ "VALUES (?1, ?2, ?3)")
				.setParameter(1, userId)
				.setParameter(2, nodeType)
				.setParameter(3, nodeId)
				.executeUpdate();
		entityManager.flush();
	}

	private void insertInterest(long userId, String topicCode, String interestType) {
		entityManager.getEntityManager()
				.createNativeQuery("INSERT INTO user_interest (user_id, topic_code, interest_type) "
						+ "VALUES (?1, ?2, ?3)")
				.setParameter(1, userId)
				.setParameter(2, topicCode)
				.setParameter(3, interestType)
				.executeUpdate();
		entityManager.flush();
	}

	private void insertKnowledgeNode(long userId, String nodeType, String nodeId,
			int clickCount, LocalDateTime lastSeenAt) {
		entityManager.getEntityManager()
				.createNativeQuery("INSERT INTO user_knowledge_nodes "
						+ "(user_id, node_label, node_type, node_id, read_article_count, "
						+ " node_click_count, first_seen_at, last_seen_at) "
						+ "VALUES (?1, '노드', ?2, ?3, 1, ?4, ?5, ?5)")
				.setParameter(1, userId)
				.setParameter(2, nodeType)
				.setParameter(3, nodeId)
				.setParameter(4, clickCount)
				.setParameter(5, lastSeenAt)
				.executeUpdate();
		entityManager.flush();
	}

	private void softDelete(long userId) {
		entityManager.getEntityManager()
				.createNativeQuery("UPDATE users SET deleted_at = NOW(6) WHERE user_id = ?1")
				.setParameter(1, userId)
				.executeUpdate();
		entityManager.flush();
	}

	@Test
	void 동기화_대상은_사용자ID_오름차순이다() {
		assertThat(repository.findSyncTargetUserIds(PageRequest.of(0, 10)))
				.containsExactly(1L, 2L, 3L);
	}

	@Test
	void 탈퇴한_사용자는_동기화_대상에서_제외한다() {
		softDelete(2L);

		assertThat(repository.findSyncTargetUserIds(PageRequest.of(0, 10)))
				.containsExactly(1L, 3L);
	}

	@Test
	void 동기화_대상을_페이지_단위로_끊어_읽는다() {
		// 한 요청에 전체 사용자를 담지 않고 나눠 보내기 위한 조회다.
		assertThat(repository.findSyncTargetUserIds(PageRequest.of(0, 2))).containsExactly(1L, 2L);
		assertThat(repository.findSyncTargetUserIds(PageRequest.of(1, 2))).containsExactly(3L);
	}

	@Test
	void 즐겨찾기한_Entity와_Story를_관심_Node로_반환한다() {
		insertNodeFavorite(1L, "ENTITY", ENTITY_ID);
		insertNodeFavorite(1L, "STORY", STORY_ID);

		assertThat(repository.findFavoriteInterestNodes(List.of(1L), INTEREST_NODE_TYPES))
				.extracting(row -> tuple(row.getUserId(), row.getNodeType(), row.getNodeId()))
				.containsExactly(
						tuple(1L, "ENTITY", ENTITY_ID),
						tuple(1L, "STORY", STORY_ID));
	}

	@Test
	void 즐겨찾기한_Event와_Statement는_관심_Node에서_제외한다() {
		// Event 는 소비 관계로 따로 전달되고, Statement 는 명세상 INTERESTED_IN 대상이 아니다.
		insertNodeFavorite(1L, "EVENT", EVENT_ID);
		insertNodeFavorite(1L, "STATEMENT", OTHER_EVENT_ID);

		assertThat(repository.findFavoriteInterestNodes(List.of(1L), INTEREST_NODE_TYPES)).isEmpty();
	}

	@Test
	void 관심_Node는_요청한_사용자의_것만_반환한다() {
		insertNodeFavorite(1L, "ENTITY", ENTITY_ID);
		insertNodeFavorite(2L, "ENTITY", STORY_ID);

		assertThat(repository.findFavoriteInterestNodes(List.of(1L), INTEREST_NODE_TYPES))
				.extracting(UserGraphAggregationRepository.InterestNodeRow::getUserId)
				.containsExactly(1L);
	}

	@Test
	void 관심과_비관심_Topic을_유형별로_나눠_반환한다() {
		insertInterest(1L, "ECONOMY", "INTEREST");
		insertInterest(1L, "SPORTS", "DISLIKE");
		insertInterest(2L, "POLITICS", "INTEREST");

		assertThat(repository.findTopicPreferences(List.of(1L, 2L), "INTEREST"))
				.extracting(row -> tuple(row.getUserId(), row.getTopicCode()))
				.containsExactly(tuple(1L, "ECONOMY"), tuple(2L, "POLITICS"));

		assertThat(repository.findTopicPreferences(List.of(1L, 2L), "DISLIKE"))
				.extracting(row -> tuple(row.getUserId(), row.getTopicCode()))
				.containsExactly(tuple(1L, "SPORTS"));
	}

	@Test
	void 클릭한_Event를_클릭수와_마지막_조회시각과_함께_반환한다() {
		LocalDateTime lastSeenAt = LocalDateTime.of(2026, 9, 15, 5, 30);
		insertKnowledgeNode(1L, "EVENT", EVENT_ID, 3, lastSeenAt);

		assertThat(repository.findConsumedEvents(List.of(1L)))
				.extracting(row -> tuple(row.getUserId(), row.getNodeId(),
						row.getClickCount(), row.getLastSeenAt()))
				.containsExactly(tuple(1L, EVENT_ID, 3, lastSeenAt));
	}

	@Test
	void 클릭하지_않은_Event는_소비로_보지_않는다() {
		// 기사를 읽기만 해도 행이 생긴다. 거르지 않으면 스쳐 간 Event 까지 소비가 된다.
		insertKnowledgeNode(1L, "EVENT", EVENT_ID, 0, LocalDateTime.of(2026, 9, 15, 5, 30));

		assertThat(repository.findConsumedEvents(List.of(1L))).isEmpty();
	}

	@Test
	void 즐겨찾기한_Event는_클릭이_없어도_보낸다() {
		// 즐겨찾기는 분명한 신호다. 여기서 빠지면 그 정보가 어디에도 전달되지 않는다.
		insertKnowledgeNode(1L, "EVENT", EVENT_ID, 0, LocalDateTime.of(2026, 9, 15, 5, 30));
		insertNodeFavorite(1L, "EVENT", EVENT_ID);

		assertThat(repository.findConsumedEvents(List.of(1L)))
				.singleElement()
				.satisfies(row -> {
					assertThat(row.getNodeId()).isEqualTo(EVENT_ID);
					assertThat(row.getFavorited()).isEqualTo(1);
				});
	}

	@Test
	void 즐겨찾기하지_않은_Event는_favorited가_거짓이다() {
		insertKnowledgeNode(1L, "EVENT", EVENT_ID, 2, LocalDateTime.of(2026, 9, 15, 5, 30));

		assertThat(repository.findConsumedEvents(List.of(1L)))
				.singleElement()
				.satisfies(row -> assertThat(row.getFavorited()).isEqualTo(0));
	}

	@Test
	void 다른_사용자의_즐겨찾기는_섞이지_않는다() {
		insertKnowledgeNode(1L, "EVENT", EVENT_ID, 2, LocalDateTime.of(2026, 9, 15, 5, 30));
		insertNodeFavorite(2L, "EVENT", EVENT_ID);

		assertThat(repository.findConsumedEvents(List.of(1L)))
				.singleElement()
				.satisfies(row -> assertThat(row.getFavorited()).isEqualTo(0));
	}

	@Test
	void Event가_아닌_Node는_소비에서_제외한다() {
		insertKnowledgeNode(1L, "ENTITY", ENTITY_ID, 5, LocalDateTime.of(2026, 9, 15, 5, 30));

		assertThat(repository.findConsumedEvents(List.of(1L))).isEmpty();
	}

	@Test
	void 소비_Event는_요청한_사용자의_것만_반환한다() {
		LocalDateTime lastSeenAt = LocalDateTime.of(2026, 9, 15, 5, 30);
		insertKnowledgeNode(1L, "EVENT", EVENT_ID, 1, lastSeenAt);
		insertKnowledgeNode(2L, "EVENT", OTHER_EVENT_ID, 1, lastSeenAt);

		assertThat(repository.findConsumedEvents(List.of(2L)))
				.extracting(row -> tuple(row.getUserId(), row.getNodeId()))
				.containsExactly(tuple(2L, OTHER_EVENT_ID));
	}
}

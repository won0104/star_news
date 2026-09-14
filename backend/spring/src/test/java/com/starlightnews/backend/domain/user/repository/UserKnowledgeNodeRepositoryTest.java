package com.starlightnews.backend.domain.user.repository;

import java.time.LocalDateTime;
import java.util.List;

import com.starlightnews.backend.domain.user.domain.UserKnowledgeNode;
import com.starlightnews.backend.domain.user.domain.UserKnowledgeNodeId;
import com.starlightnews.backend.global.enums.NodeType;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class UserKnowledgeNodeRepositoryTest {

	private static final String NODE_ID = "00000020-0920-4000-8000-000000000001";

	@Autowired
	private UserKnowledgeNodeRepository userKnowledgeNodeRepository;

	@Autowired
	private TestEntityManager entityManager;

	private UserKnowledgeNodeId id(long userId, NodeType nodeType, String nodeId) {
		return new UserKnowledgeNodeId(userId, nodeType, nodeId);
	}

	@Test
	void 첫_클릭_Row를_저장하고_복합키로_조회한다() {
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);
		UserKnowledgeNodeId id = id(1L, NodeType.EVENT, NODE_ID);

		userKnowledgeNodeRepository.save(
				UserKnowledgeNode.forFirstClick(id, "기준금리 동결", "ECONOMY", now));
		entityManager.flush();
		entityManager.clear();

		UserKnowledgeNode found = userKnowledgeNodeRepository.findById(id).orElseThrow();
		assertThat(found.getNodeLabel()).isEqualTo("기준금리 동결");
		assertThat(found.getTopicCode()).isEqualTo("ECONOMY");
		assertThat(found.getNodeClickCount()).isEqualTo(1);
		assertThat(found.getReadArticleCount()).isZero();
		assertThat(found.getFirstSeenAt()).isEqualTo(now);
		assertThat(found.getLastSeenAt()).isEqualTo(now);
	}

	@Test
	void registerClick하면_클릭수가_증가하고_lastSeenAt만_갱신된다() {
		LocalDateTime first = LocalDateTime.of(2024, 5, 25, 5, 20);
		LocalDateTime later = LocalDateTime.of(2024, 5, 26, 10, 0);
		UserKnowledgeNodeId id = id(1L, NodeType.ENTITY, NODE_ID);
		entityManager.persist(UserKnowledgeNode.forFirstClick(id, "한국은행", "ECONOMY", first));
		entityManager.flush();
		entityManager.clear();

		UserKnowledgeNode found = userKnowledgeNodeRepository.findById(id).orElseThrow();
		found.registerClick(later);
		entityManager.flush();
		entityManager.clear();

		UserKnowledgeNode reloaded = userKnowledgeNodeRepository.findById(id).orElseThrow();
		assertThat(reloaded.getNodeClickCount()).isEqualTo(2);
		assertThat(reloaded.getLastSeenAt()).isEqualTo(later);
		assertThat(reloaded.getFirstSeenAt()).isEqualTo(first);
		assertThat(reloaded.getReadArticleCount()).isZero();
	}

	@Test
	void 같은_user_같은_nodeId라도_nodeType이_다르면_다른_Row다() {
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);
		entityManager.persist(UserKnowledgeNode.forFirstClick(
				id(1L, NodeType.EVENT, NODE_ID), "이벤트", "ECONOMY", now));
		entityManager.persist(UserKnowledgeNode.forFirstClick(
				id(1L, NodeType.ENTITY, NODE_ID), "엔티티", "ECONOMY", now));
		entityManager.flush();
		entityManager.clear();

		assertThat(userKnowledgeNodeRepository.findById(id(1L, NodeType.EVENT, NODE_ID))).isPresent();
		assertThat(userKnowledgeNodeRepository.findById(id(1L, NodeType.ENTITY, NODE_ID))).isPresent();
	}

	@Test
	void topicCode가_null이어도_저장된다() {
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);
		UserKnowledgeNodeId id = id(2L, NodeType.STATEMENT, NODE_ID);

		userKnowledgeNodeRepository.save(UserKnowledgeNode.forFirstClick(id, "어떤 주장", null, now));
		entityManager.flush();
		entityManager.clear();

		assertThat(userKnowledgeNodeRepository.findById(id).orElseThrow().getTopicCode()).isNull();
	}

	@Test
	void findByUserIdAndTopicCode는_해당_사용자의_해당_토픽_노드만_반환한다() {
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);
		entityManager.persist(UserKnowledgeNode.forFirstClick(
				id(1L, NodeType.ENTITY, "00000024-0920-4000-8000-000000000001"), "한국은행", "ECONOMY", now));
		entityManager.persist(UserKnowledgeNode.forFirstClick(
				id(1L, NodeType.EVENT, "00000020-0920-4000-8000-000000000001"), "기준금리 동결", "ECONOMY", now));
		entityManager.persist(UserKnowledgeNode.forFirstClick(
				id(1L, NodeType.EVENT, "00000020-0920-4000-8000-000000000009"), "의대 증원", "SOCIETY", now));
		entityManager.persist(UserKnowledgeNode.forFirstClick(
				id(2L, NodeType.ENTITY, "00000024-0920-4000-8000-000000000002"), "다른 유저 노드", "ECONOMY", now));
		entityManager.flush();
		entityManager.clear();

		List<UserKnowledgeNode> found = userKnowledgeNodeRepository.findByUserIdAndTopicCode(1L, "ECONOMY");

		assertThat(found).extracting(UserKnowledgeNode::getNodeLabel)
				.containsExactlyInAnyOrder("한국은행", "기준금리 동결");
	}

	private UserKnowledgeNode rowWithCounts(long userId, NodeType nodeType, String nodeId, String label,
			String topicCode, int readCount, int clickCount, LocalDateTime now) {
		UserKnowledgeNode node = UserKnowledgeNode.forFirstClick(
				id(userId, nodeType, nodeId), label, topicCode, now);
		ReflectionTestUtils.setField(node, "readArticleCount", readCount);
		ReflectionTestUtils.setField(node, "nodeClickCount", clickCount);
		return node;
	}

	@Test
	void countExploredNodesByTopic는_클릭수가_0보다_큰_Node만_Topic별로_센다() {
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);
		entityManager.persist(rowWithCounts(1L, NodeType.ENTITY, "e1", "한국은행", "ECONOMY", 0, 1, now));
		entityManager.persist(rowWithCounts(1L, NodeType.EVENT, "ev1", "기준금리 동결", "ECONOMY", 0, 2, now));
		entityManager.persist(rowWithCounts(1L, NodeType.EVENT, "ev2", "클릭안함", "ECONOMY", 0, 0, now));
		entityManager.persist(rowWithCounts(1L, NodeType.EVENT, "ev3", "다른토픽", "SOCIETY", 0, 1, now));
		entityManager.persist(rowWithCounts(1L, NodeType.STATEMENT, "s1", "토픽없음", null, 0, 1, now));
		entityManager.persist(rowWithCounts(2L, NodeType.ENTITY, "e2", "다른사용자", "ECONOMY", 0, 1, now));
		entityManager.flush();
		entityManager.clear();

		List<UserKnowledgeNodeRepository.TopicNodeCount> counts = userKnowledgeNodeRepository
				.countExploredNodesByTopic(1L, List.of(NodeType.EVENT, NodeType.ENTITY, NodeType.STATEMENT));

		assertThat(counts).hasSize(2);
		assertThat(counts).filteredOn(c -> c.getTopicCode().equals("ECONOMY"))
				.singleElement().satisfies(c -> assertThat(c.getCount()).isEqualTo(2));
		assertThat(counts).filteredOn(c -> c.getTopicCode().equals("SOCIETY"))
				.singleElement().satisfies(c -> assertThat(c.getCount()).isEqualTo(1));
	}

	@Test
	void forFirstRead로_저장하면_read_article_count가_1이고_click_count는_0이다() {
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);
		UserKnowledgeNodeId id = id(1L, NodeType.EVENT, NODE_ID);

		userKnowledgeNodeRepository.save(UserKnowledgeNode.forFirstRead(id, "기준금리 동결", "ECONOMY", now));
		entityManager.flush();
		entityManager.clear();

		UserKnowledgeNode found = userKnowledgeNodeRepository.findById(id).orElseThrow();
		assertThat(found.getReadArticleCount()).isEqualTo(1);
		assertThat(found.getNodeClickCount()).isZero();
		assertThat(found.getFirstSeenAt()).isEqualTo(now);
		assertThat(found.getLastSeenAt()).isEqualTo(now);
	}

	@Test
	void upsertClick은_없던_Node를_click_count_1로_INSERT한다() {
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);
		UserKnowledgeNodeId id = id(1L, NodeType.ENTITY, NODE_ID);

		userKnowledgeNodeRepository.upsertClick(1L, "ENTITY", NODE_ID, "한국은행", "ECONOMY", now);
		entityManager.clear();

		UserKnowledgeNode found = userKnowledgeNodeRepository.findById(id).orElseThrow();
		assertThat(found.getNodeLabel()).isEqualTo("한국은행");
		assertThat(found.getNodeClickCount()).isEqualTo(1);
		assertThat(found.getReadArticleCount()).isZero();
		assertThat(found.getFirstSeenAt()).isEqualTo(now);
	}

	@Test
	void upsertClick은_기존_Node면_클릭수만_올리고_label과_firstSeenAt은_유지한다() {
		LocalDateTime first = LocalDateTime.of(2024, 5, 25, 5, 20);
		LocalDateTime later = LocalDateTime.of(2024, 5, 26, 10, 0);
		UserKnowledgeNodeId id = id(1L, NodeType.ENTITY, NODE_ID);
		entityManager.persist(UserKnowledgeNode.forFirstClick(id, "한국은행", "ECONOMY", first));
		entityManager.flush();

		userKnowledgeNodeRepository.upsertClick(1L, "ENTITY", NODE_ID, "다른 이름", "SOCIETY", later);
		entityManager.clear();

		UserKnowledgeNode reloaded = userKnowledgeNodeRepository.findById(id).orElseThrow();
		assertThat(reloaded.getNodeClickCount()).isEqualTo(2);
		assertThat(reloaded.getLastSeenAt()).isEqualTo(later);
		assertThat(reloaded.getFirstSeenAt()).isEqualTo(first);
		assertThat(reloaded.getNodeLabel()).isEqualTo("한국은행");
		assertThat(reloaded.getTopicCode()).isEqualTo("ECONOMY");
	}

	@Test
	void upsertClick은_열람으로_만들어진_Row의_read_article_count를_보존한다() {
		LocalDateTime first = LocalDateTime.of(2024, 5, 25, 5, 20);
		LocalDateTime later = LocalDateTime.of(2024, 5, 26, 10, 0);
		UserKnowledgeNodeId id = id(1L, NodeType.EVENT, NODE_ID);
		entityManager.persist(UserKnowledgeNode.forFirstRead(id, "기준금리 동결", "ECONOMY", first));
		entityManager.flush();

		userKnowledgeNodeRepository.upsertClick(1L, "EVENT", NODE_ID, "기준금리 동결", "ECONOMY", later);
		entityManager.clear();

		UserKnowledgeNode reloaded = userKnowledgeNodeRepository.findById(id).orElseThrow();
		assertThat(reloaded.getReadArticleCount()).isEqualTo(1); // 열람 신호는 그대로
		assertThat(reloaded.getNodeClickCount()).isEqualTo(1); // 클릭 신호는 따로 쌓인다
	}

	@Test
	void existsById는_다른_사용자의_같은_Node를_섞지_않는다() {
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);
		entityManager.persist(UserKnowledgeNode.forFirstClick(
				id(2L, NodeType.ENTITY, NODE_ID), "한국은행", "ECONOMY", now));
		entityManager.flush();
		entityManager.clear();

		assertThat(userKnowledgeNodeRepository.existsById(id(2L, NodeType.ENTITY, NODE_ID))).isTrue();
		assertThat(userKnowledgeNodeRepository.existsById(id(1L, NodeType.ENTITY, NODE_ID))).isFalse();
	}

	@Test
	void upsertRead는_없던_Node를_read_article_count_1로_INSERT한다() {
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);
		UserKnowledgeNodeId id = id(1L, NodeType.EVENT, NODE_ID);

		userKnowledgeNodeRepository.upsertRead(1L, "EVENT", NODE_ID, "기준금리 동결", "ECONOMY", 1, now);
		entityManager.clear();

		UserKnowledgeNode found = userKnowledgeNodeRepository.findById(id).orElseThrow();
		assertThat(found.getNodeLabel()).isEqualTo("기준금리 동결");
		assertThat(found.getTopicCode()).isEqualTo("ECONOMY");
		assertThat(found.getReadArticleCount()).isEqualTo(1);
		assertThat(found.getNodeClickCount()).isZero();
		assertThat(found.getFirstSeenAt()).isEqualTo(now);
	}

	@Test
	void upsertRead는_재열람이어도_없던_Node면_1로_시작한다() {
		LocalDateTime now = LocalDateTime.of(2024, 5, 25, 5, 20);
		UserKnowledgeNodeId id = id(1L, NodeType.EVENT, NODE_ID);

		// readIncrement=0(재열람)이어도 INSERT 되는 Row 는 이 기사가 첫 고유 기사이므로 1 이다
		userKnowledgeNodeRepository.upsertRead(1L, "EVENT", NODE_ID, "기준금리 동결", "ECONOMY", 0, now);
		entityManager.clear();

		assertThat(userKnowledgeNodeRepository.findById(id).orElseThrow().getReadArticleCount()).isEqualTo(1);
	}

	@Test
	void upsertRead는_기존_Node면_readIncrement만큼_더하고_label과_firstSeenAt은_유지한다() {
		LocalDateTime first = LocalDateTime.of(2024, 5, 25, 5, 20);
		LocalDateTime later = LocalDateTime.of(2024, 5, 26, 10, 0);
		UserKnowledgeNodeId id = id(1L, NodeType.EVENT, NODE_ID);
		entityManager.persist(UserKnowledgeNode.forFirstRead(id, "기준금리 동결", "ECONOMY", first));
		entityManager.flush();

		userKnowledgeNodeRepository.upsertRead(1L, "EVENT", NODE_ID, "다른 제목", "SOCIETY", 1, later);
		entityManager.clear();

		UserKnowledgeNode reloaded = userKnowledgeNodeRepository.findById(id).orElseThrow();
		assertThat(reloaded.getReadArticleCount()).isEqualTo(2);
		assertThat(reloaded.getLastSeenAt()).isEqualTo(later);
		assertThat(reloaded.getFirstSeenAt()).isEqualTo(first);
		assertThat(reloaded.getNodeLabel()).isEqualTo("기준금리 동결"); // 기존 Snapshot 유지
		assertThat(reloaded.getTopicCode()).isEqualTo("ECONOMY"); // 기존 대표 Topic 유지
	}

	@Test
	void upsertRead는_재열람이면_기존_Node의_고유_기사_수를_늘리지_않는다() {
		LocalDateTime first = LocalDateTime.of(2024, 5, 25, 5, 20);
		LocalDateTime later = LocalDateTime.of(2024, 5, 26, 10, 0);
		UserKnowledgeNodeId id = id(1L, NodeType.EVENT, NODE_ID);
		entityManager.persist(UserKnowledgeNode.forFirstRead(id, "기준금리 동결", "ECONOMY", first));
		entityManager.flush();

		userKnowledgeNodeRepository.upsertRead(1L, "EVENT", NODE_ID, "기준금리 동결", "ECONOMY", 0, later);
		entityManager.clear();

		UserKnowledgeNode reloaded = userKnowledgeNodeRepository.findById(id).orElseThrow();
		assertThat(reloaded.getReadArticleCount()).isEqualTo(1);
		assertThat(reloaded.getLastSeenAt()).isEqualTo(later);
	}

	@Test
	void upsertRead는_클릭으로_만들어진_Row의_click_count를_보존한다() {
		LocalDateTime first = LocalDateTime.of(2024, 5, 25, 5, 20);
		LocalDateTime later = LocalDateTime.of(2024, 5, 26, 10, 0);
		UserKnowledgeNodeId id = id(1L, NodeType.EVENT, NODE_ID);
		entityManager.persist(UserKnowledgeNode.forFirstClick(id, "기준금리 동결", "ECONOMY", first));
		entityManager.flush();

		userKnowledgeNodeRepository.upsertRead(1L, "EVENT", NODE_ID, "기준금리 동결", "ECONOMY", 1, later);
		entityManager.clear();

		UserKnowledgeNode reloaded = userKnowledgeNodeRepository.findById(id).orElseThrow();
		assertThat(reloaded.getNodeClickCount()).isEqualTo(1); // 클릭 신호는 그대로
		assertThat(reloaded.getReadArticleCount()).isEqualTo(1); // 열람 신호는 따로 쌓인다
	}
}

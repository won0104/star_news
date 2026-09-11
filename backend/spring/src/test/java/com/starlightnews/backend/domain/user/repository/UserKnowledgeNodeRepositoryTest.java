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
}

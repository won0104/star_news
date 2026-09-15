package com.starlightnews.backend.domain.usergraph;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest.InterestNode;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest.UserGraphSyncUser;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncResponse;
import com.starlightnews.backend.domain.usergraph.repository.TopicNodeIdRepository;
import com.starlightnews.backend.global.client.FastApiClient;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.verify;

/**
 * 실제 MySQL 에서 집계해 FastAPI 로 보낼 요청 본문까지 한 번에 확인한다.
 *
 * <p>조각별 테스트는 서로를 목으로 끊어 놓아서, 이어 붙였을 때 맞는지는 여기서만 드러난다.
 * FastAPI 호출과 Neo4j 조회만 목으로 막고, MySQL 집계와 조립은 실물을 쓴다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class UserGraphSyncIntegrationTest {

	private static final String SYNC_PATH = "/internal/v1/user-graph/sync";

	private static final long USER_ID = 950_101L;
	private static final long EMPTY_USER_ID = 950_102L;

	private static final String ENTITY_ID = "00000126-3001-4000-8000-000000000001";
	private static final String EVENT_ID = "00000126-3002-4000-8000-000000000002";
	private static final String ECONOMY_NODE_ID = "00000126-3003-4000-8000-000000000003";
	private static final LocalDateTime LAST_SEEN_AT = LocalDateTime.of(2026, 9, 15, 4, 30);

	@Autowired
	private com.starlightnews.backend.domain.usergraph.service.UserGraphSyncService userGraphSyncService;

	@Autowired
	private EntityManager entityManager;

	@Autowired
	private ObjectMapper objectMapper;

	@MockitoBean
	private FastApiClient fastApiClient;

	@MockitoBean
	private TopicNodeIdRepository topicNodeIdRepository;

	@BeforeEach
	void seed() {
		insertUser(USER_ID, "sync-target");
		insertUser(EMPTY_USER_ID, "sync-empty");

		nativeUpdate("INSERT INTO user_node_favorites (user_id, node_type, node_id) VALUES (?1, 'ENTITY', ?2)",
				USER_ID, ENTITY_ID);
		nativeUpdate("INSERT INTO user_interest (user_id, topic_code, interest_type) "
				+ "VALUES (?1, 'ECONOMY', 'INTEREST')", USER_ID);
		nativeUpdate("INSERT INTO user_interest (user_id, topic_code, interest_type) "
				+ "VALUES (?1, 'SPORTS', 'DISLIKE')", USER_ID);
		// 열람 4회, 클릭 2회. count 로 나가야 하는 값은 클릭 쪽이다.
		nativeUpdate("INSERT INTO user_knowledge_nodes "
						+ "(user_id, node_label, node_type, node_id, read_article_count, node_click_count, "
						+ " first_seen_at, last_seen_at) "
						+ "VALUES (?1, '이벤트', 'EVENT', ?2, 4, 2, ?3, ?3)",
				USER_ID, EVENT_ID, LAST_SEEN_AT);
		entityManager.flush();

		given(topicNodeIdRepository.findAllTopicNodeIds()).willReturn(Map.of("ECONOMY", ECONOMY_NODE_ID));
		given(fastApiClient.post(any(), any(), eq(UserGraphSyncResponse.class)))
				.willReturn(new UserGraphSyncResponse(new UserGraphSyncResponse.Data(1, 1)));
	}

	private void insertUser(long userId, String loginId) {
		nativeUpdate("INSERT INTO users (user_id, login_id, password_hash, nickname) "
				+ "VALUES (?1, ?2, 'hashed-password', ?2)", userId, loginId);
	}

	private void nativeUpdate(String sql, Object... parameters) {
		var query = entityManager.createNativeQuery(sql);
		for (int i = 0; i < parameters.length; i++) {
			query.setParameter(i + 1, parameters[i]);
		}
		query.executeUpdate();
	}

	/** 묶음이 여러 번 나갈 수 있으므로 전부 모아서 본다. */
	private List<UserGraphSyncRequest> sentRequests() {
		ArgumentCaptor<UserGraphSyncRequest> captor = ArgumentCaptor.forClass(UserGraphSyncRequest.class);
		verify(fastApiClient, atLeastOnce())
				.post(eq(SYNC_PATH), captor.capture(), eq(UserGraphSyncResponse.class));
		return captor.getAllValues();
	}

	private UserGraphSyncUser sentUser(long userId) {
		return sentRequests().stream()
				.flatMap(request -> request.users().stream())
				.filter(user -> user.userId() == userId)
				.findFirst()
				.orElseThrow(() -> new AssertionError("요청에 사용자 " + userId + " 가 없습니다"));
	}

	@Test
	void MySQL에서_집계한_상태가_요청_본문에_담긴다() {
		userGraphSyncService.sync();

		UserGraphSyncUser user = sentUser(USER_ID);

		assertThat(user.interestNodes())
				.extracting(InterestNode::nodeType, InterestNode::nodeKey)
				.containsExactlyInAnyOrder(
						tuple("ENTITY", ENTITY_ID),
						tuple("TOPIC", ECONOMY_NODE_ID));
		assertThat(user.dislikeTopicCodes()).containsExactly("SPORTS");
		assertThat(user.consumedEvents()).singleElement().satisfies(event -> {
			assertThat(event.eventId()).isEqualTo(EVENT_ID);
			assertThat(event.count()).isEqualTo(2);
		});
	}

	@Test
	void 관심_Topic은_코드가_아니라_nodeId로_나간다() {
		// FastAPI 는 MATCH (target {nodeId: nodeKey}) 로 찾는다. 코드를 보내면 조용히 누락된다.
		userGraphSyncService.sync();

		assertThat(sentUser(USER_ID).interestNodes())
				.extracting(InterestNode::nodeKey)
				.doesNotContain("ECONOMY")
				.contains(ECONOMY_NODE_ID);
	}

	@Test
	void 데이터가_없는_사용자도_빈_목록으로_포함된다() {
		// 관심을 모두 해제한 경우가 이렇게 보인다. 빼면 Neo4j 의 예전 관계가 지워지지 않는다.
		userGraphSyncService.sync();

		UserGraphSyncUser user = sentUser(EMPTY_USER_ID);

		assertThat(user.interestNodes()).isEmpty();
		assertThat(user.dislikeTopicCodes()).isEmpty();
		assertThat(user.consumedEvents()).isEmpty();
	}

	@Test
	void 직렬화한_JSON이_명세와_같은_모양이다() throws Exception {
		// FastAPI 는 camelCase 를 기대한다. 이름이 어긋나면 거절당한다.
		userGraphSyncService.sync();

		JsonNode json = objectMapper.readTree(objectMapper.writeValueAsString(sentRequests().get(0)));

		assertThat(json.fieldNames()).toIterable().containsExactlyInAnyOrder("users", "aggregatedAt");
		assertThat(json.get("users").get(0).fieldNames()).toIterable()
				.containsExactlyInAnyOrder("userId", "interestNodes", "dislikeTopicCodes", "consumedEvents");
		// 오프셋이 없으면 FastAPI 가 UTC 로 읽어 9시간 어긋난다.
		assertThat(json.get("aggregatedAt").asText()).contains("+09:00");
	}

	@Test
	void 소비_Event의_시각이_KST_오프셋으로_나간다() throws Exception {
		userGraphSyncService.sync();

		String lastViewedAt = objectMapper.valueToTree(sentUser(USER_ID))
				.get("consumedEvents").get(0).get("lastViewedAt").asText();

		assertThat(lastViewedAt).startsWith("2026-09-15T04:30").contains("+09:00");
	}
}

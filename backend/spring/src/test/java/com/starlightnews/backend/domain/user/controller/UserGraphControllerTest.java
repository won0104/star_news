package com.starlightnews.backend.domain.user.controller;

import java.time.OffsetDateTime;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.Arrays;
import java.util.List;

import com.starlightnews.backend.domain.graph.exception.GraphErrorCode;
import com.starlightnews.backend.domain.user.dto.PersonalGraphMapResponse;
import com.starlightnews.backend.domain.user.dto.PersonalGraphSummaryResponse;
import com.starlightnews.backend.domain.user.dto.PersonalNodeArticlesResponse;
import com.starlightnews.backend.domain.user.exception.PersonalGraphErrorCode;
import com.starlightnews.backend.domain.user.service.GraphNodeClickService;
import com.starlightnews.backend.domain.user.service.PersonalGraphService;
import com.starlightnews.backend.domain.user.service.PersonalNodeArticleService;
import com.starlightnews.backend.domain.user.support.GraphReadPeriod;
import com.starlightnews.backend.global.config.SecurityConfig;
import com.starlightnews.backend.global.enums.NodeType;
import com.starlightnews.backend.global.enums.TopicCode;
import com.starlightnews.backend.global.error.BusinessException;
import com.starlightnews.backend.global.error.CommonErrorCode;
import com.starlightnews.backend.global.request.RequestIdFilter;
import com.starlightnews.backend.global.security.InMemoryTokenBlacklist;
import com.starlightnews.backend.global.security.JwtProvider;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(UserGraphController.class)
@Import({SecurityConfig.class, JwtProvider.class, InMemoryTokenBlacklist.class})
@ActiveProfiles("test")
class UserGraphControllerTest {

	private static final String NODE_KEY = "00000024-0920-4000-8000-000000000001";
	private static final String CLICKS_PATH = "/api/v1/users/me/graph/nodes/ENTITY/" + NODE_KEY + "/clicks";

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private JwtProvider jwtProvider;

	@MockitoBean
	private GraphNodeClickService graphNodeClickService;

	@MockitoBean
	private PersonalGraphService personalGraphService;

	@MockitoBean
	private PersonalNodeArticleService personalNodeArticleService;

	private static final String MAP_PATH = "/api/v1/users/me/graph/map";
	private static final String SUMMARY_PATH = "/api/v1/users/me/graph";
	private static final String ARTICLES_PATH = "/api/v1/users/me/graph/nodes/ENTITY/" + NODE_KEY + "/articles";

	private String bearer() {
		return "Bearer " + jwtProvider.createAccessToken(1L);
	}

	private PersonalGraphSummaryResponse sampleSummary() {
		return new PersonalGraphSummaryResponse(
				OffsetDateTime.of(2026, 9, 11, 17, 30, 0, 0, ZoneOffset.ofHours(9)),
				List.of(
						new PersonalGraphSummaryResponse.Node(
								"topic:ECONOMY", "TOPIC_CLUSTER", null, null, "ECONOMY", "경제", 20, 1.0),
						new PersonalGraphSummaryResponse.Node(
								"ENTITY:" + NODE_KEY, "NODE", "ENTITY", NODE_KEY, "ECONOMY", "한국은행", 8, 1.0)),
				List.of(new PersonalGraphSummaryResponse.Edge(
						"topic:ECONOMY", "ENTITY:" + NODE_KEY, "BELONGS_TO_TOPIC", 1.0)));
	}

	private PersonalGraphSummaryResponse topicClusterOnlySummary() {
		List<PersonalGraphSummaryResponse.Node> topicClusters = Arrays.stream(TopicCode.values())
				.map(topic -> new PersonalGraphSummaryResponse.Node(
						"topic:" + topic.name(), "TOPIC_CLUSTER", null, null,
						topic.name(), topic.labelKo(), 0, 0.0))
				.toList();

		return new PersonalGraphSummaryResponse(
				OffsetDateTime.of(2026, 9, 11, 17, 30, 0, 0, ZoneOffset.ofHours(9)), topicClusters, List.of());
	}

	private PersonalGraphMapResponse sampleMap() {
		return new PersonalGraphMapResponse(
				OffsetDateTime.of(2026, 9, 11, 17, 30, 0, 0, ZoneOffset.ofHours(9)),
				new PersonalGraphMapResponse.TopicSummary("ECONOMY", "경제"),
				List.of(new PersonalGraphMapResponse.Node(
						"ENTITY:" + NODE_KEY, "ENTITY", NODE_KEY, "한국은행", 5, 0.91)),
				List.of(new PersonalGraphMapResponse.Edge(
						"ENTITY:" + NODE_KEY, "EVENT:ev1", "ACTOR", 0.82)));
	}

	private PersonalNodeArticlesResponse sampleArticles() {
		return new PersonalNodeArticlesResponse(
				new PersonalNodeArticlesResponse.NodeSummary("ENTITY", NODE_KEY, "한국은행"),
				List.of(new PersonalNodeArticlesResponse.Item(930001L, "한국은행, 기준금리 동결", "연합뉴스", "ECONOMY",
						OffsetDateTime.of(2026, 8, 31, 9, 10, 0, 0, ZoneOffset.ofHours(9)),
						"한국은행은 기준금리를 현재 수준으로 유지하기로 했다.", true)),
				true, "opaque-cursor");
	}

	@Test
	void 클릭_기록_성공시_200과_data_null로_응답한다() throws Exception {
		mockMvc.perform(post(CLICKS_PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data").value(nullValue()))
				.andExpect(jsonPath("$.meta.requestId").isString());

		verify(graphNodeClickService).recordClick(eq(1L), eq(NodeType.ENTITY), eq(NODE_KEY));
	}

	@Test
	void 토큰이_없으면_401이고_서비스를_호출하지_않는다() throws Exception {
		mockMvc.perform(post(CLICKS_PATH))
				.andExpect(status().isUnauthorized());

		verify(graphNodeClickService, never()).recordClick(anyLong(), any(), anyString());
	}

	@Test
	void 알_수_없는_nodeType은_400_INVALID_NODE_TYPE를_응답한다() throws Exception {
		mockMvc.perform(post("/api/v1/users/me/graph/nodes/UNKNOWN/" + NODE_KEY + "/clicks")
						.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_NODE_TYPE"));

		verify(graphNodeClickService, never()).recordClick(anyLong(), any(), anyString());
	}

	@Test
	void 클릭_기록에서_STORY는_대상이_아니라_400_INVALID_NODE_TYPE를_응답한다() throws Exception {
		mockMvc.perform(post("/api/v1/users/me/graph/nodes/STORY/" + NODE_KEY + "/clicks")
						.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_NODE_TYPE"));

		verify(graphNodeClickService, never()).recordClick(anyLong(), any(), anyString());
	}

	@Test
	void TOPIC은_개인그래프_대상이_아니라_400_INVALID_NODE_TYPE를_응답한다() throws Exception {
		mockMvc.perform(post("/api/v1/users/me/graph/nodes/TOPIC/" + NODE_KEY + "/clicks")
						.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_NODE_TYPE"));

		verify(graphNodeClickService, never()).recordClick(anyLong(), any(), anyString());
	}

	@Test
	void 서비스가_RESOURCE_NOT_FOUND를_던지면_404를_응답한다() throws Exception {
		willThrow(new BusinessException(CommonErrorCode.RESOURCE_NOT_FOUND))
				.given(graphNodeClickService).recordClick(anyLong(), any(), anyString());

		mockMvc.perform(post(CLICKS_PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"));
	}

	// --- 개인 그래프 Topic 스냅샷 ---

	@Test
	void Topic_스냅샷_조회_성공시_200과_topic_nodes_edges_구조로_응답한다() throws Exception {
		given(personalGraphService.getTopicMap(1L, "ECONOMY")).willReturn(sampleMap());

		mockMvc.perform(get(MAP_PATH).param("topicCode", "ECONOMY").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.topic.topicCode").value("ECONOMY"))
				.andExpect(jsonPath("$.data.topic.label").value("경제"))
				.andExpect(jsonPath("$.data.nodes[0].id").value("ENTITY:" + NODE_KEY))
				.andExpect(jsonPath("$.data.nodes[0].weight").value(0.91))
				.andExpect(jsonPath("$.data.edges[0].relationship").value("ACTOR"))
				.andExpect(jsonPath("$.meta.requestId").isString());
	}

	@Test
	void Topic_스냅샷에_기간을_전달한다() throws Exception {
		GraphReadPeriod period = new GraphReadPeriod(LocalDate.of(2026, 9, 1), LocalDate.of(2026, 9, 30));
		given(personalGraphService.getTopicMap(1L, "ECONOMY", period)).willReturn(sampleMap());

		mockMvc.perform(get(MAP_PATH).param("topicCode", "ECONOMY")
				.param("from", "2026-09-01").param("to", "2026-09-30")
				.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk());

		verify(personalGraphService).getTopicMap(1L, "ECONOMY", period);
	}

	@Test
	void topicCode_쿼리파라미터가_없으면_400을_응답한다() throws Exception {
		mockMvc.perform(get(MAP_PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest());

		verify(personalGraphService, never()).getTopicMap(anyLong(), anyString());
	}

	@Test
	void 서비스가_INVALID_TOPIC_CODE를_던지면_400을_응답한다() throws Exception {
		given(personalGraphService.getTopicMap(anyLong(), anyString()))
				.willThrow(new BusinessException(PersonalGraphErrorCode.INVALID_TOPIC_CODE));

		mockMvc.perform(get(MAP_PATH).param("topicCode", "NOPE").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_TOPIC_CODE"));
	}

	@Test
	void Topic_스냅샷_조회는_토큰이_없으면_401이다() throws Exception {
		mockMvc.perform(get(MAP_PATH).param("topicCode", "ECONOMY"))
				.andExpect(status().isUnauthorized());

		verify(personalGraphService, never()).getTopicMap(anyLong(), anyString());
	}

	// --- 개인 그래프 요약 ---

	@Test
	void 요약_조회_성공시_200과_클러스터_노드_엣지_구조로_응답한다() throws Exception {
		given(personalGraphService.getSummary(1L)).willReturn(sampleSummary());

		mockMvc.perform(get(SUMMARY_PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.nodes[0].id").value("topic:ECONOMY"))
				.andExpect(jsonPath("$.data.nodes[0].kind").value("TOPIC_CLUSTER"))
				.andExpect(jsonPath("$.data.nodes[1].id").value("ENTITY:" + NODE_KEY))
				.andExpect(jsonPath("$.data.nodes[1].kind").value("NODE"))
				.andExpect(jsonPath("$.data.edges[0].relationship").value("BELONGS_TO_TOPIC"))
				.andExpect(jsonPath("$.meta.requestId").isString());
	}

	@Test
	void 요약에_기간을_전달하고_누락이나_역순은_거부한다() throws Exception {
		GraphReadPeriod period = new GraphReadPeriod(LocalDate.of(2026, 9, 1), LocalDate.of(2026, 9, 30));
		given(personalGraphService.getSummary(1L, period)).willReturn(sampleSummary());

		mockMvc.perform(get(SUMMARY_PATH).param("from", "2026-09-01").param("to", "2026-09-30")
				.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk());
		verify(personalGraphService).getSummary(1L, period);

		mockMvc.perform(get(SUMMARY_PATH).param("from", "2026-09-01")
				.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));
		mockMvc.perform(get(SUMMARY_PATH).param("from", "2026-09-30").param("to", "2026-09-01")
				.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));
	}

	@Test
	void 개인_노드가_없어도_모든_Topic_Cluster를_응답한다() throws Exception {
		given(personalGraphService.getSummary(1L)).willReturn(topicClusterOnlySummary());

		mockMvc.perform(get(SUMMARY_PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.nodes.length()").value(TopicCode.values().length))
				.andExpect(jsonPath("$.data.nodes[0].id").value("topic:POLITICS"))
				.andExpect(jsonPath("$.data.nodes[0].kind").value("TOPIC_CLUSTER"))
				.andExpect(jsonPath("$.data.nodes[0].nodeType").doesNotExist())
				.andExpect(jsonPath("$.data.edges").isEmpty());
	}

	@Test
	void 요약_조회는_토큰이_없으면_401이다() throws Exception {
		mockMvc.perform(get(SUMMARY_PATH))
				.andExpect(status().isUnauthorized());

		verify(personalGraphService, never()).getSummary(anyLong());
	}

	// --- 개인 그래프 노드별 읽은 기사 ---

	@Test
	void 읽은_기사_조회_성공시_200과_node_items_구조로_응답한다() throws Exception {
		given(personalNodeArticleService.getReadArticles(eq(1L), eq(NodeType.ENTITY), eq(NODE_KEY), eq(20), any()))
				.willReturn(sampleArticles());

		mockMvc.perform(get(ARTICLES_PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk())
				.andExpect(header().exists(RequestIdFilter.HEADER_NAME))
				.andExpect(jsonPath("$.data.node.nodeType").value("ENTITY"))
				.andExpect(jsonPath("$.data.node.title").value("한국은행"))
				.andExpect(jsonPath("$.data.items[0].articleId").value(930001))
				.andExpect(jsonPath("$.data.items[0].organizationName").value("연합뉴스"))
				.andExpect(jsonPath("$.data.items[0].lastReadAt").value("2026-08-31T09:10:00+09:00"))
				.andExpect(jsonPath("$.data.items[0].bookmarked").value(true))
				.andExpect(jsonPath("$.data.hasNext").value(true))
				.andExpect(jsonPath("$.data.nextCursor").value("opaque-cursor"))
				.andExpect(jsonPath("$.meta.requestId").isString());

		verify(personalNodeArticleService).getReadArticles(eq(1L), eq(NodeType.ENTITY), eq(NODE_KEY), eq(20), isNull());
	}

	@Test
	void 노드별_읽은_기사에도_같은_기간을_전달한다() throws Exception {
		GraphReadPeriod period = new GraphReadPeriod(LocalDate.of(2026, 9, 1), LocalDate.of(2026, 9, 30));
		given(personalNodeArticleService.getReadArticles(1L, NodeType.ENTITY, NODE_KEY, 5, null, period))
				.willReturn(sampleArticles());

		mockMvc.perform(get(ARTICLES_PATH).param("size", "5")
				.param("from", "2026-09-01").param("to", "2026-09-30")
				.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk());
		verify(personalNodeArticleService).getReadArticles(1L, NodeType.ENTITY, NODE_KEY, 5, null, period);
	}

	@Test
	void size와_cursor_쿼리파라미터를_서비스에_전달한다() throws Exception {
		given(personalNodeArticleService.getReadArticles(any(), any(), any(), anyInt(), any()))
				.willReturn(sampleArticles());

		mockMvc.perform(get(ARTICLES_PATH).param("size", "5").param("cursor", "opaque-cursor")
						.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isOk());

		verify(personalNodeArticleService).getReadArticles(
				eq(1L), eq(NodeType.ENTITY), eq(NODE_KEY), eq(5), eq("opaque-cursor"));
	}

	@Test
	void size가_1미만이면_400_INVALID_INPUT_VALUE를_응답한다() throws Exception {
		mockMvc.perform(get(ARTICLES_PATH).param("size", "0").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));

		verify(personalNodeArticleService, never()).getReadArticles(any(), any(), any(), anyInt(), any());
	}

	@Test
	void size가_50초과면_400_INVALID_INPUT_VALUE를_응답한다() throws Exception {
		mockMvc.perform(get(ARTICLES_PATH).param("size", "51").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_INPUT_VALUE"));
	}

	@Test
	void STORY는_개인_관련기사_대상이_아니라_400_INVALID_NODE_TYPE를_응답한다() throws Exception {
		mockMvc.perform(get("/api/v1/users/me/graph/nodes/STORY/" + NODE_KEY + "/articles")
						.header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_NODE_TYPE"));

		verify(personalNodeArticleService, never()).getReadArticles(any(), any(), any(), anyInt(), any());
	}

	@Test
	void 서비스가_INVALID_CURSOR를_던지면_400을_응답한다() throws Exception {
		given(personalNodeArticleService.getReadArticles(any(), any(), any(), anyInt(), any()))
				.willThrow(new BusinessException(GraphErrorCode.INVALID_CURSOR));

		mockMvc.perform(get(ARTICLES_PATH).param("cursor", "broken").header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("INVALID_CURSOR"));
	}

	@Test
	void 서비스가_NODE_NOT_ACQUIRED를_던지면_404를_응답한다() throws Exception {
		given(personalNodeArticleService.getReadArticles(any(), any(), any(), anyInt(), any()))
				.willThrow(new BusinessException(PersonalGraphErrorCode.NODE_NOT_ACQUIRED));

		mockMvc.perform(get(ARTICLES_PATH).header(HttpHeaders.AUTHORIZATION, bearer()))
				.andExpect(status().isNotFound())
				.andExpect(jsonPath("$.code").value("NODE_NOT_ACQUIRED"));
	}

	@Test
	void 읽은_기사_조회는_토큰이_없으면_401이다() throws Exception {
		mockMvc.perform(get(ARTICLES_PATH))
				.andExpect(status().isUnauthorized());

		verify(personalNodeArticleService, never()).getReadArticles(any(), any(), any(), anyInt(), any());
	}
}

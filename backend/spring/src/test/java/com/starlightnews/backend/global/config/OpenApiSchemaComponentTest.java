package com.starlightnews.backend.global.config;

import java.util.ArrayList;
import java.util.List;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(properties = "springdoc.api-docs.enabled=true")
@AutoConfigureMockMvc
@ActiveProfiles("test")
class OpenApiSchemaComponentTest {

	@Autowired
	private MockMvc mockMvc;

	@Autowired
	private ObjectMapper objectMapper;

	@Test
	void 중첩_DTO는_응답별_고유_스키마를_참조한다() throws Exception {
		String document = mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andReturn()
				.getResponse()
				.getContentAsString();
		JsonNode schemas = objectMapper.readTree(document).path("components").path("schemas");

		assertArrayItemRef(schemas, "RelatedArticlesResponse", "articles", "RelatedArticleItem");
		assertArrayItemRef(schemas, "RecommendationBoardResponse", "items", "RecommendationBoardItem");
		assertArrayItemRef(schemas, "ArticleHistoryResponse", "items", "ArticleHistoryItem");
		assertRef(schemas, "NewsReportResponse", "period", "NewsReportPeriod");
		assertArrayItemRef(schemas, "NewsReportResponse", "sourceReads", "NewsReportSourceRead");
		assertArrayItemRef(schemas, "NewsReportResponse", "weeklyTopicTrend", "NewsReportWeeklyTopicTrend");
		assertArrayItemRef(schemas, "NewsReportWeeklyTopicTrend", "topics", "NewsReportWeeklyTopic");
		assertArrayItemRef(schemas, "NewsReportResponse", "topicLandscape", "NewsReportTopicLandscapeNode");
		assertThat(schemas.path("NewsReportTopicLandscapeNode").path("properties")
				.has("userReadArticleCount")).isTrue();
		assertThat(schemas.path("NewsReportTopicLandscapeNode").path("properties")
				.has("globalReadArticleCount")).isTrue();
		assertThat(schemas.path("NewsReportTopicLandscapeNode").path("properties").has("x")).isTrue();
		assertThat(schemas.path("NewsReportTopicLandscapeNode").path("properties").has("y")).isTrue();
		assertThat(schemas.path("NewsReportTopicLandscapeNode").path("properties").has("strong")).isTrue();
		assertThat(schemas.path("NewsReportTopicLandscapeNode").path("properties")
				.has("readArticleCount")).isFalse();
		assertRef(schemas, "PersonalNodeArticlesResponse", "node", "PersonalNodeArticleNodeSummary");
		assertArrayItemRef(schemas, "PersonalNodeArticlesResponse", "items", "PersonalNodeArticleItem");
		assertArrayItemRef(schemas, "PersonalGraphMapResponse", "nodes", "PersonalGraphMapNode");
		assertArrayItemRef(schemas, "PersonalGraphMapResponse", "edges", "PersonalGraphMapEdge");
		assertArrayItemRef(schemas, "PersonalGraphSummaryResponse", "nodes", "PersonalGraphSummaryNode");
		assertArrayItemRef(schemas, "PersonalGraphSummaryResponse", "edges", "PersonalGraphSummaryEdge");
		assertThat(schemas.path("PersonalGraphSummaryNode").path("properties").has("type")).isFalse();
		assertRef(schemas, "GraphNeighborsResponse", "centerNode", "GraphNeighborNodeSummary");
		assertArrayItemRef(schemas, "GraphNeighborsResponse", "nodes", "GraphNeighborNodeSummary");
		assertArrayItemRef(schemas, "GraphNeighborsResponse", "edges", "GraphNeighborEdge");
		assertRef(schemas, "TopicExplorationResponse", "centerTopic", "TopicExplorationCenterTopic");
		assertArrayItemRef(
				schemas, "TopicExplorationResponse", "entryNodes", "TopicExplorationEntryNode");

		assertThat(schemas.has("Item")).isFalse();
		assertThat(schemas.has("Node")).isFalse();
		assertThat(schemas.has("Edge")).isFalse();
		assertThat(schemas.has("NodeSummary")).isFalse();

		assertEnumValues(schemas, "ArticleSummaryResponse", "summaryStatus");
		assertThat(schemas.path("ArticleDetailResponse").path("properties").has("summary")).isFalse();
		assertThat(schemas.path("ArticleDetailResponse").path("properties").has("summaryStatus")).isFalse();
		assertThat(schemas.path("ArticleHistoryItem")
				.path("properties")
				.path("clickCount")
				.path("description")
				.asText())
				.isEqualTo("사용자가 이 기사를 열람한 횟수 (뉴스 카드 클릭 기준)");
	}

	@Test
	void 공개_Home_API는_인증을_요구하지_않는다() throws Exception {
		String document = mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andReturn()
				.getResponse()
				.getContentAsString();
		JsonNode security = objectMapper.readTree(document)
				.path("paths")
				.path("/api/v1/home")
				.path("get")
				.path("security");

		assertThat(security.isArray()).isTrue();
		assertThat(security).isEmpty();
	}

	@Test
	void 공개_Topic별_탐색_API는_인증을_요구하지_않는다() throws Exception {
		String document = mockMvc.perform(get("/v3/api-docs"))
				.andExpect(status().isOk())
				.andReturn()
				.getResponse()
				.getContentAsString();
		JsonNode security = objectMapper.readTree(document)
				.path("paths")
				.path("/api/v1/topics/{topicCode}/exploration")
				.path("get")
				.path("security");

		assertThat(security.isArray()).isTrue();
		assertThat(security).isEmpty();
	}

	private void assertEnumValues(JsonNode schemas, String responseSchema, String property) {
		List<String> values = new ArrayList<>();
		schemas.path(responseSchema)
				.path("properties")
				.path(property)
				.path("enum")
				.forEach(value -> values.add(value.asText()));

		assertThat(values).containsExactly("PROCESSING", "COMPLETED");
	}

	private void assertRef(JsonNode schemas, String responseSchema, String property, String componentSchema) {
		String ref = schemas.path(responseSchema)
				.path("properties")
				.path(property)
				.path("$ref")
				.asText();

		assertThat(ref).isEqualTo("#/components/schemas/" + componentSchema);
		assertThat(schemas.has(componentSchema)).isTrue();
	}

	private void assertArrayItemRef(JsonNode schemas, String responseSchema, String property,
			String componentSchema) {
		String ref = schemas.path(responseSchema)
				.path("properties")
				.path(property)
				.path("items")
				.path("$ref")
				.asText();

		assertThat(ref).isEqualTo("#/components/schemas/" + componentSchema);
		assertThat(schemas.has(componentSchema)).isTrue();
	}
}

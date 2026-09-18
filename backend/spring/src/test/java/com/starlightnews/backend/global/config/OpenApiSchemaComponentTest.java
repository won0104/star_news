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
		assertRef(schemas, "PersonalNodeArticlesResponse", "node", "PersonalNodeArticleNodeSummary");
		assertArrayItemRef(schemas, "PersonalNodeArticlesResponse", "items", "PersonalNodeArticleItem");
		assertArrayItemRef(schemas, "PersonalGraphMapResponse", "nodes", "PersonalGraphMapNode");
		assertArrayItemRef(schemas, "PersonalGraphMapResponse", "edges", "PersonalGraphMapEdge");
		assertArrayItemRef(schemas, "PersonalGraphSummaryResponse", "nodes", "PersonalGraphSummaryNode");
		assertArrayItemRef(schemas, "PersonalGraphSummaryResponse", "edges", "PersonalGraphSummaryEdge");
		assertRef(schemas, "GraphNeighborsResponse", "centerNode", "GraphNeighborNodeSummary");
		assertArrayItemRef(schemas, "GraphNeighborsResponse", "nodes", "GraphNeighborNodeSummary");
		assertArrayItemRef(schemas, "GraphNeighborsResponse", "edges", "GraphNeighborEdge");

		assertThat(schemas.has("Item")).isFalse();
		assertThat(schemas.has("Node")).isFalse();
		assertThat(schemas.has("Edge")).isFalse();
		assertThat(schemas.has("NodeSummary")).isFalse();

		assertEnumValues(schemas, "ArticleSummaryResponse", "summaryStatus");
		assertEnumValues(schemas, "ArticleDetailResponse", "summaryStatus");
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

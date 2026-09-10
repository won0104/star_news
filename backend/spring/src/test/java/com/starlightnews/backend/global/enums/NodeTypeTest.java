package com.starlightnews.backend.global.enums;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class NodeTypeTest {

	@Test
	void 정상_코드는_대소문자와_공백을_무시하고_변환된다() {
		assertThat(NodeType.from("EVENT")).contains(NodeType.EVENT);
		assertThat(NodeType.from(" event ")).contains(NodeType.EVENT);
		assertThat(NodeType.from("Article")).contains(NodeType.ARTICLE);
	}

	@Test
	void 추천_투영_전용인_USER나_알_수_없는_값은_빈_Optional이다() {
		assertThat(NodeType.from("USER")).isEmpty();
		assertThat(NodeType.from("CONCEPT")).isEmpty();
		assertThat(NodeType.from("UNKNOWN")).isEmpty();
		assertThat(NodeType.from(null)).isEmpty();
		assertThat(NodeType.from("   ")).isEmpty();
	}

	@Test
	void 값_목록은_공통_Enum_NODE_TYPE_7개와_일치한다() {
		assertThat(NodeType.values())
				.extracting(Enum::name)
				.containsExactlyInAnyOrder("ARTICLE", "EVENT", "STORY", "TOPIC", "ENTITY", "TIME", "STATEMENT");
	}

	@Test
	void 유형별_Label과_속성_매핑이_스키마와_일치한다() {
		assertThat(NodeType.ARTICLE.label()).isEqualTo("Article");
		assertThat(NodeType.ARTICLE.titleProperty()).isEqualTo("title");
		assertThat(NodeType.ARTICLE.timeProperty()).isEqualTo("publishedAt");

		assertThat(NodeType.EVENT.titleProperty()).isEqualTo("title");
		assertThat(NodeType.EVENT.timeProperty()).isEqualTo("occurredAt");
		assertThat(NodeType.EVENT.typeProperty()).isNull();

		assertThat(NodeType.STORY.timeProperty()).isEqualTo("lastEventAt");

		assertThat(NodeType.ENTITY.titleProperty()).isEqualTo("canonicalName");
		assertThat(NodeType.ENTITY.typeProperty()).isEqualTo("entityType");

		assertThat(NodeType.TOPIC.titleProperty()).isEqualTo("nameKo");

		assertThat(NodeType.STATEMENT.titleProperty()).isEqualTo("text");
		assertThat(NodeType.STATEMENT.typeProperty()).isEqualTo("statementType");

		assertThat(NodeType.TIME.titleProperty()).isEqualTo("value");
		assertThat(NodeType.TIME.typeProperty()).isEqualTo("granularity");
	}
}

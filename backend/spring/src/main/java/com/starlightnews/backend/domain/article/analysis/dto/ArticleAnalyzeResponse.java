package com.starlightnews.backend.domain.article.analysis.dto;

/**
 * FastAPI {@code POST /internal/v1/articles/analyze} 응답. FastAPI 는 결과를 {@code data} 로 감싼다.
 */
public record ArticleAnalyzeResponse(Data data) {

	/**
	 * @param articleNodeId    Neo4j Article 의 nodeId. articles.node_id 에 넣는다
	 * @param primaryTopicCode 대분류. articles.topic_code 에 넣는다
	 * @param subtopicCode     소분류. articles.subtopic_code 에 넣는다
	 */
	public record Data(
			long articleId,
			String articleNodeId,
			String status,
			String primaryTopicCode,
			String subtopicCode
	) {
	}
}

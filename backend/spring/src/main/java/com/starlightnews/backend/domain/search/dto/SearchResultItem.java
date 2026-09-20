package com.starlightnews.backend.domain.search.dto;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 검색 결과 목록의 Node 요약. 선택 이후 상세 조회는 공용 Graph API가 담당한다.
 */
public record SearchResultItem(

		@Schema(description = "Node 유형 (EVENT·ENTITY·STATEMENT)", example = "EVENT")
		String nodeType,

		@Schema(description = "Neo4j 내부 ID가 아닌 Node 업무 ID(nodeId)",
				example = "00000020-0920-4000-8000-000000000001")
		String nodeKey,

		@Schema(description = "Node 유형별 원본 표시 속성", example = "한국은행 기준금리 동결")
		String label
) {
}

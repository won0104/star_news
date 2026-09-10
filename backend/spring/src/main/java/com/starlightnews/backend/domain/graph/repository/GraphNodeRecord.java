package com.starlightnews.backend.domain.graph.repository;

import java.time.ZonedDateTime;

/**
 * Neo4j 에서 조회한 그래프 Node 의 화면 표시용 원시 값.
 * title 은 Node 이름 속성, type 은 세부 유형/시간 단위, time 은 대표 시각이며 type·time 은 없을 수 있다.
 */
public record GraphNodeRecord(
		String title,
		String type,
		ZonedDateTime time
) {
}

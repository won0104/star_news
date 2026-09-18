package com.starlightnews.backend.domain.home.dto;

import java.time.OffsetDateTime;
import java.util.List;

import com.starlightnews.backend.global.enums.NodeType;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 공개된 최신 트렌드 집계 회차와 순위 목록. 그래프·개인화 정보는 포함하지 않는다.
 */
public record HomeResponse(

		@Schema(description = "트렌드 공개 회차 시각 (06:00/18:00 KST). 기사 집계 기준은 한 시간 전이며, 공개된 트렌드가 없으면 null",
				example = "2026-09-15T18:00:00+09:00", nullable = true)
		OffsetDateTime snapshotAt,

		@Schema(description = "순위 오름차순의 오늘의 트렌드 목록 (최대 10개)")
		List<Item> trends
) {

	@Schema(name = "HomeTrendItem", description = "오늘의 트렌드 항목")
	public record Item(

			@Schema(description = "개별 트렌드 항목 ID", example = "101")
			long trendItemId,

			@Schema(description = "집계 회차 내 순위", example = "1")
			int rank,

			@Schema(description = "공통 Node 유형", example = "EVENT")
			NodeType nodeType,

			@Schema(description = "Neo4j 내부 ID가 아닌 Node의 업무 ID인 nodeId",
					example = "550e8400-e29b-41d4-a716-446655440000")
			String nodeKey,

			@Schema(description = "집계 시점에 저장한 Node 표시 이름", example = "한국은행 기준금리 동결")
			String label,

			@Schema(description = "공개 시각 한 시간 전을 기준으로 직전 24시간의 고유 대표 기사 수", example = "23")
			int articleCount
	) {
	}
}

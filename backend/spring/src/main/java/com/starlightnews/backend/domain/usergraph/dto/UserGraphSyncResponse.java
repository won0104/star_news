package com.starlightnews.backend.domain.usergraph.dto;

import java.util.List;

/**
 * {@code POST /internal/v1/user-graph/sync} 응답 본문.
 *
 * <p>FastAPI 는 결과를 {@code data} 로 한 겹 감싸서 돌려준다.
 *
 * <p>{@code updatedUsers} 가 {@code processedUsers} 보다 적은 이유는 두 가지다. 이미 최신이라 건너뛴
 * 사용자와, {@code failed} 에 실린 실패한 사용자다. 앞은 정상이고 뒤는 추적해야 한다.
 */
public record UserGraphSyncResponse(Data data) {

	public record Data(int processedUsers, int updatedUsers, List<Failure> failed) {

		public Data {
			failed = failed == null ? List.of() : List.copyOf(failed);
		}
	}

	/** 반영하지 못한 사용자와 사유. code 는 FastAPI 의 오류 코드다(예: GRAPH_REFERENCE_NOT_FOUND). */
	public record Failure(Long userId, String code) {
	}

	public int processedUsers() {
		return data == null ? 0 : data.processedUsers();
	}

	public int updatedUsers() {
		return data == null ? 0 : data.updatedUsers();
	}

	public List<Failure> failures() {
		return data == null ? List.of() : data.failed();
	}
}

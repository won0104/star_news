package com.starlightnews.backend.domain.usergraph.dto;

/**
 * {@code POST /internal/v1/user-graph/sync} 응답 본문.
 *
 * <p>FastAPI 는 결과를 {@code data} 로 한 겹 감싸서 돌려준다.
 *
 * <p>{@code updatedUsers} 가 {@code processedUsers} 보다 적으면, 그만큼은 이미 최신이라 건너뛴
 * 사용자다. 실패가 아니다.
 */
public record UserGraphSyncResponse(Data data) {

	public record Data(int processedUsers, int updatedUsers) {
	}

	public int processedUsers() {
		return data == null ? 0 : data.processedUsers();
	}

	public int updatedUsers() {
		return data == null ? 0 : data.updatedUsers();
	}
}

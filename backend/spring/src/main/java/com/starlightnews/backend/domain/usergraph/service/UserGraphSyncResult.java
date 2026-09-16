package com.starlightnews.backend.domain.usergraph.service;

/**
 * 동기화 묶음 하나의 결과.
 *
 * @param processedUsers FastAPI 가 받아 처리한 사용자 수
 * @param updatedUsers   실제로 그래프가 바뀐 사용자 수. 이미 최신이면 처리는 되고 갱신은 안 된다
 * @param failedUsers    전달하지 못한 사용자 수
 */
public record UserGraphSyncResult(int processedUsers, int updatedUsers, int failedUsers) {

	public static UserGraphSyncResult empty() {
		return new UserGraphSyncResult(0, 0, 0);
	}

	public static UserGraphSyncResult failed(int userCount) {
		return new UserGraphSyncResult(0, 0, userCount);
	}

	/** 이미 최신이라 건너뛴 경우. 실패가 아니므로 failedUsers 는 0 이다. */
	public static UserGraphSyncResult alreadyUpToDate(int userCount) {
		return new UserGraphSyncResult(userCount, 0, 0);
	}

	public UserGraphSyncResult plus(UserGraphSyncResult other) {
		return new UserGraphSyncResult(
				processedUsers + other.processedUsers(),
				updatedUsers + other.updatedUsers(),
				failedUsers + other.failedUsers());
	}
}

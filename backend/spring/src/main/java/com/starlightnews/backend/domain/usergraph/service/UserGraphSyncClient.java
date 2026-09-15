package com.starlightnews.backend.domain.usergraph.service;

import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncRequest;
import com.starlightnews.backend.domain.usergraph.dto.UserGraphSyncResponse;
import com.starlightnews.backend.global.client.FastApiClient;
import com.starlightnews.backend.global.client.InternalApiErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 조립한 요청을 FastAPI 로 보낸다.
 *
 * <p>묶음 하나가 실패해도 예외를 올리지 않고 결과로 알린다. 회차 전체를 무너뜨리는 대신 나머지 묶음을
 * 계속 보내기 위해서다. 수집 배치에서 카테고리 하나의 실패를 격리한 것과 같은 방식이다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserGraphSyncClient {

	private static final String SYNC_PATH = "/internal/v1/user-graph/sync";

	private final FastApiClient fastApiClient;

	/**
	 * 사용자 묶음 하나를 동기화한다.
	 *
	 * @return 처리 결과. 실패해도 예외를 던지지 않는다
	 */
	public UserGraphSyncResult send(UserGraphSyncRequest request) {
		int userCount = request.users().size();
		if (userCount == 0) {
			return UserGraphSyncResult.empty();
		}

		try {
			UserGraphSyncResponse response =
					fastApiClient.post(SYNC_PATH, request, UserGraphSyncResponse.class);
			logFailedUsers(response);
			return new UserGraphSyncResult(
					response.processedUsers(), response.updatedUsers(), response.failures().size());
		} catch (BusinessException failure) {
			return handle(failure, userCount);
		}
	}

	/**
	 * 요청은 성공했지만 일부 사용자가 반영되지 않은 경우를 남긴다.
	 *
	 * <p>대부분 참조가 끊긴 경우다. MySQL 에 남은 Node ID 가 Neo4j 에서 사라지면 그 사용자는 고치기
	 * 전까지 계속 실패하므로, 누구인지 로그에 남겨야 추적할 수 있다.
	 */
	private void logFailedUsers(UserGraphSyncResponse response) {
		if (response.failures().isEmpty()) {
			return;
		}

		log.warn("User Graph 에 반영하지 못한 사용자가 있습니다. ({}명: {})",
				response.failures().size(),
				response.failures().stream()
						.map(failure -> failure.userId() + "=" + failure.code())
						.toList());
	}

	private UserGraphSyncResult handle(BusinessException failure, int userCount) {
		if (failure.getErrorCode() == InternalApiErrorCode.INTERNAL_API_CONFLICT) {
			// 보낸 스냅샷보다 최신 상태가 이미 있다. 할 일이 없었을 뿐 실패가 아니다.
			log.info("User Graph 가 이미 최신입니다. (사용자 {}명)", userCount);
			return UserGraphSyncResult.alreadyUpToDate(userCount);
		}

		log.warn("User Graph 동기화 실패 (사용자 {}명, 원인={})", userCount, failure.getErrorCode().getCode());
		return UserGraphSyncResult.failed(userCount);
	}
}

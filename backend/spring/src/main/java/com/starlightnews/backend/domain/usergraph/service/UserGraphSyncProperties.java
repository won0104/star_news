package com.starlightnews.backend.domain.usergraph.service;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * User Graph 동기화 배치 설정.
 *
 * @param chunkSize 한 요청에 담을 사용자 수. 사용자 단위로만 나눈다. 한 사용자를 두 요청으로 쪼개면
 *                  FastAPI 가 앞 요청의 관계를 지우기 때문에, 이 값이 얼마든 사용자는 쪼개지 않는다.
 */
@Validated
@ConfigurationProperties(prefix = "app.user-graph")
public record UserGraphSyncProperties(
		@Min(1) @Max(1000) int chunkSize
) {

	private static final int DEFAULT_CHUNK_SIZE = 100;

	public UserGraphSyncProperties {
		chunkSize = chunkSize == 0 ? DEFAULT_CHUNK_SIZE : chunkSize;
	}
}

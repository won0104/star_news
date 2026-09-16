package com.starlightnews.backend.global.client;

import lombok.RequiredArgsConstructor;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

/**
 * FastAPI 연결 상태를 actuator 헬스체크에 노출한다.
 *
 * <p>기사 분석·추천 계산이 FastAPI 를 거치므로, 배포 후 두 서버가 실제로 통신되는지 확인할 수단이 필요하다.
 *
 * <p>내부 API 키가 없는 환경에서는 연결을 확인하지 않고 UNKNOWN 으로 둔다. AI 연동이 필요 없는 팀원의
 * 로컬에서 앱 전체가 DOWN 으로 보이면 안 되기 때문이다.
 */
@Component
@RequiredArgsConstructor
public class FastApiHealthIndicator implements HealthIndicator {

	private final FastApiClient fastApiClient;
	private final FastApiProperties properties;

	@Override
	public Health health() {
		if (!properties.isConfigured()) {
			return Health.unknown()
					.withDetail("reason", "내부 API 키가 설정되지 않아 확인하지 않음")
					.build();
		}

		Health.Builder builder = fastApiClient.isReachable() ? Health.up() : Health.down();
		return builder.withDetail("baseUrl", properties.baseUrl()).build();
	}
}

package com.starlightnews.backend.domain.usergraph;

import com.starlightnews.backend.domain.usergraph.service.UserGraphSyncProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * User Graph 동기화 설정.
 *
 * <p>스케줄링 활성화는 기사 수집 쪽에서 이미 켜 두었으므로 여기서 다시 켜지 않는다.
 */
@Configuration
@EnableConfigurationProperties(UserGraphSyncProperties.class)
public class UserGraphConfig {
}

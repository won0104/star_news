package com.starlightnews.backend.global.config;

import org.junit.jupiter.api.Test;
import org.neo4j.driver.Driver;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.env.Environment;
import org.springframework.data.neo4j.core.Neo4jClient;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Neo4j 자동설정이 로드되고 spring.neo4j.* 값이 바인딩되는지 확인한다(빈 배선 검증).
 * bolt 연결은 지연 초기화되므로 여기서 실제 접속은 시도하지 않는다.
 * 서버 인스턴스 연결 검증은 배포 후 /actuator/health 의 neo4j 컴포넌트로 한다.
 */
@SpringBootTest
@ActiveProfiles("test")
class Neo4jConfigTest {

	@Autowired
	private Driver neo4jDriver;

	@Autowired
	private Neo4jClient neo4jClient;

	@Autowired
	private Environment environment;

	@Test
	void Neo4j_빈이_생성되고_URI가_설정에서_바인딩된다() {
		assertThat(neo4jDriver).isNotNull();
		assertThat(neo4jClient).isNotNull();
		assertThat(environment.getProperty("spring.neo4j.uri")).startsWith("bolt://");
	}
}

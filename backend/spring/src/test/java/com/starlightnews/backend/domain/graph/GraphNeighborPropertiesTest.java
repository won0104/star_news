package com.starlightnews.backend.domain.graph;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 주변 그래프 순위 설정이 application.properties 값으로 묶이는지 본다.
 *
 * <p>기준값이 잘못 들어가면 허브가 결과를 먹거나(너무 큼) 멀쩡한 Node 까지 잘린다(너무 작음).
 */
@SpringBootTest
@ActiveProfiles("test")
class GraphNeighborPropertiesTest {

	@Autowired
	private GraphNeighborProperties properties;

	@Test
	void 기본값이_적용된다() {
		assertThat(properties.hubThreshold()).isEqualTo(50);
		assertThat(properties.traverseThreshold()).isEqualTo(300);
		assertThat(properties.placeWeight()).isEqualTo(0.6);
		assertThat(properties.timeWeight()).isEqualTo(0.3);
		assertThat(properties.supportWeight()).isEqualTo(0.1);
		assertThat(properties.recencyHalfLifeDays()).isEqualTo(7.0);
	}

	@Test
	void 경유_기준이_감점_기준보다_높다() {
		// 경유 기준을 감점 기준까지 낮추면 2홉 Node 가 통째로 사라진다. Entity 대부분이 그 사이에 있다.
		assertThat(properties.traverseThreshold()).isGreaterThan(properties.hubThreshold());
	}
}

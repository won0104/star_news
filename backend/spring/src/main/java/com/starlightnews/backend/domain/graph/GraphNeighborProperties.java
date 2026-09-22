package com.starlightnews.backend.domain.graph;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * 주변 그래프 순위 계산 설정.
 *
 * <p>기사에서 뽑은 그래프는 "미국"·"한국" 같은 Entity 가 수천 갈래로 연결된다. 아무 사건에서나 이
 * 노드를 거쳐 아무 사건으로 갈 수 있어, 손대지 않으면 탐색이 같은 자리를 맴돈다.
 *
 * @param hubThreshold      이 연결 수를 넘는 만큼 점수를 깎기 시작한다
 * @param traverseThreshold 이 연결 수를 넘는 Node 는 2홉 경유지로 쓰지 않는다. 결과에는 남는다
 * @param placeWeight       장소 관계({@code PLACE}) 가중치
 * @param timeWeight        시점 관계({@code OCCURRED_ON}) 가중치
 * @param supportWeight     뒷받침하는 기사 수를 반영하는 정도
 * @param recencyHalfLifeDays 이 날수가 지나면 최신성 가중치가 절반이 된다
 */
@Validated
@ConfigurationProperties(prefix = "app.graph.neighbor")
public record GraphNeighborProperties(
		@Min(1) int hubThreshold,
		@Min(1) int traverseThreshold,
		@Positive double placeWeight,
		@Positive double timeWeight,
		@Positive double supportWeight,
		@Positive double recencyHalfLifeDays
) {

	private static final int DEFAULT_HUB_THRESHOLD = 50;
	private static final int DEFAULT_TRAVERSE_THRESHOLD = 300;
	private static final double DEFAULT_PLACE_WEIGHT = 0.6;
	private static final double DEFAULT_TIME_WEIGHT = 0.3;
	private static final double DEFAULT_SUPPORT_WEIGHT = 0.1;
	private static final double DEFAULT_RECENCY_HALF_LIFE_DAYS = 7.0;

	public GraphNeighborProperties {
		hubThreshold = hubThreshold == 0 ? DEFAULT_HUB_THRESHOLD : hubThreshold;
		traverseThreshold = traverseThreshold == 0 ? DEFAULT_TRAVERSE_THRESHOLD : traverseThreshold;
		placeWeight = placeWeight == 0 ? DEFAULT_PLACE_WEIGHT : placeWeight;
		timeWeight = timeWeight == 0 ? DEFAULT_TIME_WEIGHT : timeWeight;
		supportWeight = supportWeight == 0 ? DEFAULT_SUPPORT_WEIGHT : supportWeight;
		recencyHalfLifeDays = recencyHalfLifeDays == 0
				? DEFAULT_RECENCY_HALF_LIFE_DAYS : recencyHalfLifeDays;
	}
}

package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import java.time.OffsetDateTime;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.hibernate.validator.constraints.time.DurationMin;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * 지난 구간의 기사를 한 번에 채워 넣는 설정.
 *
 * <p>정시 수집은 호출 시점의 헤드라인만 가져오므로, 배치가 돌지 못한 구간은 그냥 비어 있게 된다.
 * top-headlines 가 {@code from}·{@code to} 를 받으므로 그 구간을 따로 훑어 메운다.
 *
 * <p>일회성 작업이라 HTTP 경로를 새로 열지 않고 {@link GNewsBackfillRunner} 가 기동 시 한 번만
 * 실행한다. {@code .env} 로 켜고 재시작했다가, 끝나면 다시 끄면 된다.
 *
 * @param from             채울 구간의 시작. {@code 2026-09-26T00:00:00Z} 처럼 오프셋까지 적는다
 * @param to               채울 구간의 끝
 * @param slice            한 번에 요청할 구간 길이. 요청당 기사 수에 상한(max)이 있어 구간이 넓으면
 *                         앞부분만 돌아온다. 좁히면 빠짐이 줄고 요청 수가 는다
 * @param maxPagesPerSlice 한 구간에서 넘겨볼 최대 페이지 수. 응답이 max 만큼 꽉 차면 다음 장을
 *                         부르는데, 상한이 없으면 구간을 잘못 잡았을 때 요청을 끝없이 태운다
 */
@Validated
@ConfigurationProperties(prefix = "app.gnews.backfill")
public record GNewsBackfillProperties(
		boolean enabled,
		OffsetDateTime from,
		OffsetDateTime to,
		@DurationMin(minutes = 10) Duration slice,
		@Min(1) @Max(20) int maxPagesPerSlice
) {

	private static final Duration DEFAULT_SLICE = Duration.ofHours(6);
	private static final int DEFAULT_MAX_PAGES = 3;

	public GNewsBackfillProperties {
		slice = slice == null ? DEFAULT_SLICE : slice;
		maxPagesPerSlice = maxPagesPerSlice == 0 ? DEFAULT_MAX_PAGES : maxPagesPerSlice;
	}

	/**
	 * 실행할 수 있는 설정인지.
	 *
	 * <p>켜져 있는데 구간이 없거나 거꾸로면 실행하지 않는다. 기동을 막지는 않는다 — 백필은 곁다리
	 * 작업이라 설정 실수로 서비스가 안 뜨는 쪽이 더 나쁘다.
	 */
	public boolean isRunnable() {
		return enabled && from != null && to != null && from.isBefore(to);
	}
}

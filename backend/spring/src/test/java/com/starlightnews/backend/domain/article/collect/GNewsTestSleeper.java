package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/** 재시도 대기를 실제로 자지 않고 기록만 해, 대기 시간이 의도대로 늘어나는지 검증한다. */
class GNewsTestSleeper implements GNewsClient.Sleeper {

	final List<Duration> waits = new ArrayList<>();

	@Override
	public void sleep(Duration duration) {
		waits.add(duration);
	}
}

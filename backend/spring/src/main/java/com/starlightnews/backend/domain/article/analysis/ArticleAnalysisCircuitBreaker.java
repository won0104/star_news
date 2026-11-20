package com.starlightnews.backend.domain.article.analysis;

import java.time.LocalDateTime;
import java.time.ZoneId;

import com.starlightnews.backend.domain.article.analysis.ArticleAnalysisBatchResult.StopReason;
import com.starlightnews.backend.global.client.FastApiClient;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * AI 워커 장애가 회차를 넘겨 이어질 때, 매 회차 죽은 워커를 다시 두드리지 않게 막는다.
 *
 * <p>회차 안에서는 연속 5건 실패하면 멈추지만({@link StopReason#TOO_MANY_FAILURES}), 다음 정시 회차는
 * 그 사실을 모르고 또 5건을 부른다. 장애가 몇 시간 이어지면 매시간 5건씩 시도 횟수를 태워 멀쩡한 기사가
 * FAILED 로 굳는다. 그래서 연속 실패로 멈춘 회차가 나오면 차단을 걸고, 다음 회차부터는 기사를 부르기 전에
 * FastAPI 헬스체크를 먼저 본다.
 *
 * <ul>
 *   <li>닫힘: 평소대로 돈다.</li>
 *   <li>열림 + 헬스체크 실패: 기사를 하나도 건드리지 않고 회차를 건너뛴다.</li>
 *   <li>열림 + 헬스체크 통과: 시험 회차로 돈다. FastAPI 의 {@code /health} 는 AI 워커까지 확인하지 않아
 *       통과만으로는 워커가 살아났는지 알 수 없다. 그래서 첫 실패 한 번에 멈추게 해 태우는 기사를
 *       한 건으로 줄이고, 워커가 응답하면 평소 한도로 돌아간다. 회차가 연속 실패로 끝나지 않으면 닫는다.</li>
 * </ul>
 *
 * <p><b>상태는 메모리에만 둔다.</b> 재시작하면 닫힘으로 돌아가 첫 회차가 다시 최대 5건을 부를 수 있다.
 * 인스턴스마다 상태가 따로지만 분석 배치는 분산 잠금으로 한 인스턴스에서만 돌아, 회차를 연달아 같은
 * 인스턴스가 잡으면 그대로 이어진다. 다른 인스턴스가 잡으면 그쪽은 닫힘에서 시작해 한 회차만큼(최대 5건)
 * 더 부를 수 있다. 이 정도 손해를 막자고 상태를 DB 에 두는 것보다 단순함을 택했다.
 *
 * <p>분석 회차는 스케줄러가 한 번에 하나만 돌리므로 상태는 한 스레드만 바꾼다. 다른 스레드(지표 조회)가
 * 읽을 수 있어 {@code volatile} 로 둔다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ArticleAnalysisCircuitBreaker {

	private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

	private final FastApiClient fastApiClient;

	/** 차단을 건 시각. 닫혀 있으면 null. */
	private volatile LocalDateTime openedAt;

	/** 회차를 어떻게 돌릴지 정한다. 열려 있으면 헬스체크를 부른다. */
	public Decision beforeRound() {
		if (openedAt == null) {
			return Decision.RUN;
		}
		if (fastApiClient.isReachable()) {
			log.info("기사 분석: FastAPI 가 응답해 시험 회차를 돕니다. (차단 시작 {})", openedAt);
			return Decision.PROBE;
		}
		return Decision.SKIP;
	}

	/**
	 * 끝난 회차 결과로 상태를 바꾼다. 예외로 끊긴 회차는 워커 상태를 말해 주지 않으므로 부르지 않는다.
	 *
	 * @return 상태가 바뀌었으면 그 방향
	 */
	public Transition afterRound(StopReason stopReason) {
		boolean failing = stopReason == StopReason.TOO_MANY_FAILURES;
		if (failing && openedAt == null) {
			openedAt = LocalDateTime.now(SEOUL);
			log.error("기사 분석: 연속 실패로 차단을 겁니다. 다음 회차부터 헬스체크가 통과할 때만 분석합니다.");
			return Transition.OPENED;
		}
		if (!failing && openedAt != null) {
			log.info("기사 분석: 시험 회차가 성공해 차단을 풉니다. (차단 시작 {})", openedAt);
			openedAt = null;
			return Transition.CLOSED;
		}
		return Transition.NONE;
	}

	public boolean isOpen() {
		return openedAt != null;
	}

	/** 차단을 건 시각. 닫혀 있으면 null. */
	public LocalDateTime openedAt() {
		return openedAt;
	}

	/** 회차를 어떻게 돌릴지. */
	public enum Decision {

		/** 닫혀 있다. 평소대로 돈다. */
		RUN,

		/** 열려 있지만 헬스체크가 통과했다. 첫 실패에 멈추는 시험 회차로 돈다. */
		PROBE,

		/** 열려 있고 헬스체크도 실패했다. 기사를 건드리지 않고 건너뛴다. */
		SKIP
	}

	/** 회차가 끝난 뒤 상태가 바뀐 방향. */
	public enum Transition {
		NONE,
		OPENED,
		CLOSED
	}
}

package com.starlightnews.backend.domain.recommendation.service;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import com.starlightnews.backend.domain.recommendation.domain.RecommendationParameter;
import com.starlightnews.backend.domain.recommendation.dto.RecommendationRetuneResponse;
import com.starlightnews.backend.domain.recommendation.repository.RecommendationParameterRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 주 1회 추천 가중치를 다시 고른다.
 *
 * <p>FastAPI 가 그리드서치로 계산한 값을 받아 이력으로 쌓는다. 다음 추천 회차부터 새 값이 쓰인다.
 *
 * <p>실패하면 아무것도 저장하지 않고 기존 가중치를 그대로 둔다. 재시도하지 않고 다음 주를 기다린다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationRetuneService {

	private static final BigDecimal MIN_WEIGHT = BigDecimal.ZERO;
	private static final BigDecimal MAX_WEIGHT = BigDecimal.ONE;

	private final RecommendationRetuneClient retuneClient;
	private final RecommendationParameterRepository parameterRepository;

	/**
	 * 재튜닝을 한 번 수행한다.
	 *
	 * @return 새 가중치를 저장했으면 true
	 */
	@Transactional
	public boolean retune(LocalDateTime now) {
		return retuneClient.retune()
				.filter(this::isUsable)
				.map(data -> save(data, now))
				.orElse(false);
	}

	private boolean save(RecommendationRetuneResponse.Data data, LocalDateTime now) {
		parameterRepository.save(new RecommendationParameter(data.cbfWeight(), data.cfWeight(),
				data.ndcgAt10(), data.hitRateAt10(), data.recallAt10(), now));

		log.info("추천 가중치 재튜닝: cbf {} / cf {} (nDCG@10 {}, HitRate@10 {}, Recall@10 {})",
				data.cbfWeight(), data.cfWeight(), data.ndcgAt10(), data.hitRateAt10(), data.recallAt10());
		return true;
	}

	/**
	 * 받은 가중치를 쓸 수 있는지 본다.
	 *
	 * <p>이상한 값을 그대로 저장하면 다음 재튜닝까지 일주일 동안 그 값으로 추천이 나간다. 범위를
	 * 벗어나면 저장하지 않고 기존 값을 유지한다.
	 */
	private boolean isUsable(RecommendationRetuneResponse.Data data) {
		if (!inRange(data.cbfWeight()) || !inRange(data.cfWeight())) {
			log.warn("재튜닝 결과를 쓰지 않습니다. 가중치가 0~1 범위 밖입니다. (cbf={}, cf={})",
					data.cbfWeight(), data.cfWeight());
			return false;
		}
		return true;
	}

	private boolean inRange(BigDecimal weight) {
		return weight != null
				&& weight.compareTo(MIN_WEIGHT) >= 0
				&& weight.compareTo(MAX_WEIGHT) <= 0;
	}
}

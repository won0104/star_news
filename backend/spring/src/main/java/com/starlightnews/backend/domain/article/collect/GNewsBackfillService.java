package com.starlightnews.backend.domain.article.collect;

import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.exception.ArticleCollectErrorCode;
import com.starlightnews.backend.domain.article.service.ArticleStoreService;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 지난 구간의 기사를 훑어 저장한다.
 *
 * <p>구간을 {@code slice} 단위로 쪼개 카테고리마다 훑는다. 쪼개는 이유는 요청당 기사 수에 상한이
 * 있어서다 — 사흘치를 한 번에 달라고 하면 최신 100건만 돌아오고 나머지는 조용히 빠진다.
 *
 * <p>전처리와 저장은 정시 수집과 똑같은 경로({@link CollectedArticlePreprocessor},
 * {@link ArticleStoreService})를 쓴다. 백필만 다른 규칙으로 들어오면 같은 DB 안에 품질이 다른
 * 기사가 섞인다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class GNewsBackfillService {

	private final GNewsClient gNewsClient;
	private final CollectedArticlePreprocessor preprocessor;
	private final ArticleStoreService articleStoreService;
	private final GNewsProperties properties;
	private final GNewsBackfillProperties backfillProperties;

	/**
	 * 설정한 구간을 채운다.
	 *
	 * <p>최신 구간부터 거슬러 올라간다. 분석 대기열이 먼저 저장된 기사부터 처리하므로, 최신 기사가
	 * 먼저 분석돼 화면에 빨리 뜬다.
	 *
	 * @return 새로 저장한 기사 수
	 */
	public int backfill() {
		if (!properties.isConfigured()) {
			log.info("기사 백필: GNews API 키가 없어 건너뜁니다.");
			return 0;
		}
		if (!backfillProperties.isRunnable()) {
			log.warn("기사 백필: 구간 설정이 올바르지 않아 건너뜁니다. (from={}, to={})",
					backfillProperties.from(), backfillProperties.to());
			return 0;
		}

		List<Slice> slices = slices();
		log.info("기사 백필 시작: {} ~ {}, 구간 {}개 (구간 길이 {}, 카테고리 {}개)",
				backfillProperties.from(), backfillProperties.to(), slices.size(),
				backfillProperties.slice(), properties.categories().size());

		int totalStored = 0;
		int done = 0;
		for (Slice slice : slices) {
			if (Thread.currentThread().isInterrupted()) {
				log.warn("기사 백필: 종료 신호를 받아 {}개 구간을 남기고 멈춥니다.", slices.size() - done);
				break;
			}

			Fetched fetched = fetch(slice);
			if (!fetched.articles().isEmpty()) {
				totalStored += articleStoreService.store(preprocessor.process(fetched.articles()));
			}
			done++;
			log.info("기사 백필 진행: {}/{} 구간 완료 ({} ~ {}), 이번 구간 수집 {}건, 누적 신규 {}건",
					done, slices.size(), slice.from(), slice.to(), fetched.articles().size(), totalStored);

			if (fetched.exhausted()) {
				log.warn("기사 백필: 요청 한도가 소진돼 {}개 구간을 남기고 멈춥니다.", slices.size() - done);
				break;
			}
		}

		log.info("기사 백필 종료: 구간 {}/{} 처리, 신규 {}건", done, slices.size(), totalStored);
		return totalStored;
	}

	/** 최신 구간이 앞에 오도록 쪼갠다. 마지막 구간은 남은 길이만큼만 잡는다. */
	private List<Slice> slices() {
		Duration length = backfillProperties.slice();
		List<Slice> slices = new java.util.ArrayList<>();
		OffsetDateTime end = backfillProperties.to();
		while (end.isAfter(backfillProperties.from())) {
			OffsetDateTime start = end.minus(length);
			if (start.isBefore(backfillProperties.from())) {
				start = backfillProperties.from();
			}
			slices.add(new Slice(start, end));
			end = start;
		}
		return List.copyOf(slices);
	}

	/**
	 * 구간 하나를 카테고리마다 훑는다.
	 *
	 * <p>카테고리 사이 중복은 url 해시로 한 번만 남긴다. 같은 기사가 general 과 business 에 동시에
	 * 올라오는 일이 흔하다.
	 */
	private Fetched fetch(Slice slice) {
		Map<String, CollectedArticle> byUrlHash = new LinkedHashMap<>();
		for (String category : properties.categories()) {
			if (Thread.currentThread().isInterrupted()) {
				break;
			}
			if (!fetchCategory(category, slice, byUrlHash)) {
				return new Fetched(List.copyOf(byUrlHash.values()), true);
			}
		}
		return new Fetched(List.copyOf(byUrlHash.values()), false);
	}

	/**
	 * 카테고리 하나를 페이지를 넘기며 훑는다.
	 *
	 * <p>응답이 {@code max} 만큼 꽉 차면 아직 남았다고 보고 다음 장을 부른다. 덜 차면 그 구간은 끝이다.
	 *
	 * @return 백필을 계속해도 되면 true. 요청 한도·인증 문제면 false
	 */
	private boolean fetchCategory(String category, Slice slice,
			Map<String, CollectedArticle> byUrlHash) {
		for (int page = 1; page <= backfillProperties.maxPagesPerSlice(); page++) {
			List<CollectedArticle> articles;
			try {
				articles = gNewsClient.fetchTopHeadlines(category,
						new GNewsClient.Window(slice.from(), slice.to(), page));
			} catch (BusinessException failure) {
				if (isExhausted(failure.getErrorCode())) {
					// 남은 카테고리도 전부 실패한다. 요청을 더 태우지 않는다.
					log.warn("기사 백필: 호출이 막혀 중단합니다. (category={}, code={})",
							category, failure.getErrorCode().getCode());
					return false;
				}
				log.warn("기사 백필: 구간 수집 실패, 건너뜁니다. (category={}, page={}, code={})",
						category, page, failure.getErrorCode().getCode());
				return true;
			}

			articles.forEach(article -> byUrlHash.putIfAbsent(
					HexFormat.of().formatHex(article.urlHash()), article));

			if (articles.size() < properties.max()) {
				return true;
			}
		}
		log.info("기사 백필: 페이지 상한({})까지 채워 일부가 빠질 수 있습니다. (category={}, {} ~ {})",
				backfillProperties.maxPagesPerSlice(), category, slice.from(), slice.to());
		return true;
	}

	private boolean isExhausted(com.starlightnews.backend.global.error.ErrorCode errorCode) {
		return errorCode == ArticleCollectErrorCode.NEWS_SOURCE_QUOTA_EXCEEDED
				|| errorCode == ArticleCollectErrorCode.NEWS_SOURCE_UNAUTHORIZED;
	}

	/** 한 번에 요청할 구간. */
	private record Slice(OffsetDateTime from, OffsetDateTime to) {
	}

	/**
	 * 구간 하나의 수집 결과.
	 *
	 * @param exhausted 요청 한도가 소진돼 더 부를 수 없는지
	 */
	private record Fetched(List<CollectedArticle> articles, boolean exhausted) {
	}
}

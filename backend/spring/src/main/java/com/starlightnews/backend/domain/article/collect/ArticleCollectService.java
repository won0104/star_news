package com.starlightnews.backend.domain.article.collect;

import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import com.starlightnews.backend.domain.article.exception.ArticleCollectErrorCode;
import com.starlightnews.backend.global.error.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * GNews 카테고리를 돌며 저장 가능한 기사를 모은다.
 *
 * <p>같은 기사가 여러 카테고리(general 과 business 등)에 동시에 올라오므로 url 해시로 한 번만 남긴다.
 * 카테고리 하나가 실패해도 나머지는 계속 수집한다 — 한 카테고리 때문에 그 회차 전체를 버릴 이유가 없다.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ArticleCollectService {

	private final GNewsClient gNewsClient;
	private final GNewsProperties properties;

	/** @return 카테고리 간 중복을 제거한 수집 결과. 수집할 수 없으면 빈 목록 */
	public List<CollectedArticle> collectAll() {
		if (!properties.isConfigured()) {
			log.info("GNews API 키가 없어 기사 수집을 건너뜁니다.");
			return List.of();
		}

		Map<String, CollectedArticle> byUrlHash = new LinkedHashMap<>();
		for (String category : properties.categories()) {
			if (Thread.currentThread().isInterrupted() || !collectCategory(category, byUrlHash)) {
				break;
			}
		}

		log.info("기사 수집 완료: {}건 (카테고리 {}개)", byUrlHash.size(), properties.categories().size());
		return List.copyOf(byUrlHash.values());
	}

	/** @return 다음 카테고리를 계속 수집해도 되면 true */
	private boolean collectCategory(String category, Map<String, CollectedArticle> byUrlHash) {
		try {
			List<CollectedArticle> articles = gNewsClient.fetchTopHeadlines(category);
			for (CollectedArticle article : articles) {
				// 먼저 수집된 카테고리를 유지한다. 어느 쪽을 남기든 기사 내용은 같다.
				boolean added = byUrlHash.putIfAbsent(
						HexFormat.of().formatHex(article.urlHash()), article) == null;
				if (log.isDebugEnabled()) {
					log.debug("수집 {} | {} | {} | {}자 | {} | {}",
							added ? "신규" : "중복", category, article.contentType(),
							article.content().length(), article.organizationName(), article.title());
				}
			}
			log.info("카테고리 수집: category={}, 응답={}건", category, articles.size());
			return true;
		} catch (BusinessException failure) {
			if (failure.getErrorCode() == ArticleCollectErrorCode.NEWS_SOURCE_UNAUTHORIZED) {
				log.warn("GNews 인증 실패로 이번 회차 수집을 중단합니다. (category={})", category);
				return false;
			}
			if (failure.getErrorCode() == ArticleCollectErrorCode.NEWS_SOURCE_QUOTA_EXCEEDED) {
				// 쿼터가 바닥나면 남은 카테고리도 전부 실패한다. 요청을 더 태우지 않고 멈춘다.
				log.warn("GNews 요청 한도 초과로 이번 회차 수집을 중단합니다. (category={})", category);
				return false;
			}
			log.warn("GNews 카테고리 수집 실패, 건너뜁니다. (category={}, code={})",
					category, failure.getErrorCode().getCode());
			return true;
		}
	}
}

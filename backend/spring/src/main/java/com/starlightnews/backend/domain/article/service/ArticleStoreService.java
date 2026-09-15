package com.starlightnews.backend.domain.article.service;

import java.util.List;

import com.starlightnews.backend.domain.article.dto.CollectedArticle;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 수집한 기사를 MySQL 에 저장한다.
 *
 * <p>기사 한 건이 실패해도 나머지는 계속 저장한다. 한 회차에 100건 안팎을 다루는데 한 건 때문에
 * 그 회차를 통째로 버리면 다음 주기까지 아무것도 쌓이지 않는다. 트랜잭션도 기사 단위로 나뉜다
 * ({@link ArticleWriter}).
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ArticleStoreService {

	private final ArticleWriter articleWriter;

	/**
	 * @return 이번에 새로 저장한 기사 수. 이미 있던 기사와 실패한 기사는 세지 않는다
	 */
	public int store(List<CollectedArticle> articles) {
		int newlyStored = 0;
		int skipped = 0;
		int failed = 0;

		for (CollectedArticle article : articles) {
			try {
				if (articleWriter.write(article)) {
					newlyStored++;
				} else {
					skipped++;
				}
			} catch (RuntimeException failure) {
				failed++;
				log.warn("기사 저장 실패, 건너뜁니다. (url={}, 원인={})", article.url(), failure.toString());
			}
		}

		log.info("기사 저장 완료: 신규 {}건, 기존 {}건, 실패 {}건 (전체 {}건)",
				newlyStored, skipped, failed, articles.size());
		return newlyStored;
	}
}
